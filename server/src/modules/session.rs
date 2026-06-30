use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use anyhow::{Result, anyhow};
use futures_util::stream::{SplitSink, SplitStream};
use futures_util::{SinkExt, StreamExt};
use tokio::net::TcpStream;
use tokio::sync::mpsc;
use tokio::task::JoinHandle;
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::{WebSocketStream, accept_async};
use webrtc::ice_transport::ice_candidate::RTCIceCandidateInit;
use webrtc::media::Sample;
use webrtc::peer_connection::RTCPeerConnection;
use webrtc::peer_connection::sdp::session_description::RTCSessionDescription;
use webrtc::track::track_local::track_local_static_sample::TrackLocalStaticSample;

use crate::modules::capture::{EncodedFrame, spawn_capture_thread};
use crate::modules::config::{FRAME_CHANNEL_CAPACITY, frame_fps};
use crate::modules::signaling::Signal;
use crate::modules::webrtc::build_peer_connection;

type WsSink = SplitSink<WebSocketStream<TcpStream>, Message>;
type WsStream = SplitStream<WebSocketStream<TcpStream>>;

pub async fn handle_peer(stream: TcpStream) -> Result<()> {
    let ws = accept_async(stream).await?;
    let (ws_sink, ws_stream) = ws.split();

    let (pc, track) = build_peer_connection().await?;
    let (out_tx, out_rx) = mpsc::unbounded_channel::<Signal>();

    forward_ice_candidates(&pc, out_tx.clone());
    send_initial_offer(&pc, &out_tx).await?;

    let writer_task = spawn_signaling_writer(ws_sink, out_rx);
    let reader_task = spawn_signaling_reader(ws_stream, Arc::clone(&pc));

    let stop = Arc::new(AtomicBool::new(false));
    let (frame_tx, frame_rx) = mpsc::channel::<EncodedFrame>(FRAME_CHANNEL_CAPACITY);
    let capture_thread = spawn_capture_thread(frame_tx, Arc::clone(&stop));

    println!("peer connected, streaming H.264 via shared memory");
    pump_frames_to_track(frame_rx, &track).await;

    stop.store(true, Ordering::Relaxed);
    let _ = capture_thread.join();
    reader_task.abort();
    writer_task.abort();
    let _ = pc.close().await;
    Ok(())
}

fn forward_ice_candidates(pc: &Arc<RTCPeerConnection>, tx: mpsc::UnboundedSender<Signal>) {
    pc.on_ice_candidate(Box::new(move |candidate| {
        let tx = tx.clone();
        Box::pin(async move {
            let Some(c) = candidate else { return };
            let Ok(init) = c.to_json() else { return };
            let _ = tx.send(Signal::Candidate {
                candidate: init.candidate,
                sdp_mid: init.sdp_mid,
                sdp_mline_index: init.sdp_mline_index,
            });
        })
    }));
}

async fn send_initial_offer(
    pc: &Arc<RTCPeerConnection>,
    tx: &mpsc::UnboundedSender<Signal>,
) -> Result<()> {
    let offer = pc.create_offer(None).await?;
    pc.set_local_description(offer.clone()).await?;
    tx.send(Signal::Offer { sdp: offer.sdp })
        .map_err(|_| anyhow!("signaling channel closed"))?;
    Ok(())
}

fn spawn_signaling_writer(
    mut sink: WsSink,
    mut rx: mpsc::UnboundedReceiver<Signal>,
) -> JoinHandle<()> {
    tokio::spawn(async move {
        while let Some(signal) = rx.recv().await {
            let Ok(text) = serde_json::to_string(&signal) else {
                continue;
            };
            if sink.send(Message::Text(text.into())).await.is_err() {
                break;
            }
        }
    })
}

fn spawn_signaling_reader(mut stream: WsStream, pc: Arc<RTCPeerConnection>) -> JoinHandle<()> {
    tokio::spawn(async move {
        while let Some(msg) = stream.next().await {
            let Ok(msg) = msg else { break };
            let Message::Text(text) = msg else { continue };
            let Ok(signal) = serde_json::from_str::<Signal>(&text) else {
                continue;
            };
            match signal {
                Signal::Answer { sdp } => {
                    if let Ok(desc) = RTCSessionDescription::answer(sdp) {
                        let _ = pc.set_remote_description(desc).await;
                    }
                }
                Signal::Candidate {
                    candidate,
                    sdp_mid,
                    sdp_mline_index,
                } => {
                    let _ = pc
                        .add_ice_candidate(RTCIceCandidateInit {
                            candidate,
                            sdp_mid,
                            sdp_mline_index,
                            username_fragment: None,
                        })
                        .await;
                }
                Signal::Offer { .. } => {}
            }
        }
    })
}

async fn pump_frames_to_track(
    mut frame_rx: mpsc::Receiver<EncodedFrame>,
    track: &Arc<TrackLocalStaticSample>,
) {
    let fallback_dur = Duration::from_millis(1000 / u64::from(frame_fps()));
    let mut last_captured: Option<std::time::Instant> = None;
    while let Some(frame) = frame_rx.recv().await {
        let duration = match last_captured {
            Some(prev) => frame.captured_at.saturating_duration_since(prev),
            None => fallback_dur,
        };
        let duration = if duration.is_zero() {
            fallback_dur
        } else {
            duration
        };
        last_captured = Some(frame.captured_at);
        if track
            .write_sample(&Sample {
                data: frame.data.into(),
                duration,
                ..Default::default()
            })
            .await
            .is_err()
        {
            break;
        }
    }
}
