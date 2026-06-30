use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use anyhow::{Result, anyhow};
use tokio::sync::mpsc;
use windows::Win32::Foundation::{CloseHandle, HANDLE};
use windows::Win32::System::Memory::{
    FILE_MAP_READ, MEMORY_MAPPED_VIEW_ADDRESS, MapViewOfFile, OpenFileMappingW, UnmapViewOfFile,
};
use windows::core::PCWSTR;

use crate::modules::config::frame_fps;
use crate::modules::mf_encoder::MfH264Encoder;
use crate::modules::pixel::even_dim;

pub struct EncodedFrame {
    pub data: Vec<u8>,
    pub captured_at: Instant,
}

const SHM_NAME: &str = "yolo_frame_shm";
const SHM_MAX_W: usize = 1920;
const SHM_MAX_H: usize = 1080;
const SHM_HEADER_SIZE: usize = 16;
const SHM_DATA_SIZE: usize = SHM_MAX_W * SHM_MAX_H * 4;

struct ShmReader {
    handle: HANDLE,
    view: MEMORY_MAPPED_VIEW_ADDRESS,
    ptr: *const u8,
}

unsafe impl Send for ShmReader {}

impl ShmReader {
    fn open() -> Result<Self> {
        let name: Vec<u16> = SHM_NAME.encode_utf16().chain(std::iter::once(0)).collect();
        let handle = unsafe {
            OpenFileMappingW(
                FILE_MAP_READ.0,
                false,
                PCWSTR::from_raw(name.as_ptr()),
            )
        }
        .map_err(|e| anyhow!("OpenFileMappingW: {e}"))?;

        let view = unsafe { MapViewOfFile(handle, FILE_MAP_READ, 0, 0, 0) };
        if view.Value.is_null() {
            unsafe { let _ = CloseHandle(handle); }
            return Err(anyhow!("MapViewOfFile returned null"));
        }

        Ok(Self {
            ptr: view.Value.cast(),
            handle,
            view,
        })
    }

    fn read_u32(&self, offset: usize) -> u32 {
        let bytes: [u8; 4] =
            unsafe { self.ptr.add(offset).cast::<[u8; 4]>().read_unaligned() };
        u32::from_le_bytes(bytes)
    }

    fn read_header(&self) -> (u32, u32, u32, u32) {
        (
            self.read_u32(0),
            self.read_u32(4),
            self.read_u32(8),
            self.read_u32(12),
        )
    }

    fn pixel_slice(&self, byte_len: usize) -> &[u8] {
        unsafe { std::slice::from_raw_parts(self.ptr.add(SHM_HEADER_SIZE), byte_len) }
    }
}

impl Drop for ShmReader {
    fn drop(&mut self) {
        unsafe {
            let _ = UnmapViewOfFile(self.view);
            let _ = CloseHandle(self.handle);
        }
    }
}

pub fn spawn_capture_thread(
    frame_tx: mpsc::Sender<EncodedFrame>,
    stop: Arc<AtomicBool>,
) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        let mut encoder: Option<MfH264Encoder> = None;
        let mut encoder_dims: Option<(u32, u32)> = None;
        let mut last_seq: u32 = 0;
        let poll_interval = Duration::from_millis(5);
        let stale_timeout = Duration::from_secs(5);

        'outer: loop {
            if stop.load(Ordering::Relaxed) || frame_tx.is_closed() {
                return;
            }

            let shm = match ShmReader::open() {
                Ok(s) => s,
                Err(_) => {
                    std::thread::sleep(Duration::from_millis(500));
                    continue;
                }
            };

            eprintln!("shm reader connected to {SHM_NAME}");
            let mut last_frame_time = Instant::now();

            loop {
                if stop.load(Ordering::Relaxed) || frame_tx.is_closed() {
                    return;
                }

                let (seq, raw_w, raw_h, stride) = shm.read_header();

                if seq == last_seq || seq == 0 || raw_w == 0 || raw_h == 0 {
                    if last_frame_time.elapsed() > stale_timeout && last_seq != 0 {
                        eprintln!("shm stale, reopening");
                        last_seq = 0;
                        continue 'outer;
                    }
                    std::thread::sleep(poll_interval);
                    continue;
                }

                let width = even_dim(raw_w as usize) as u32;
                let height = even_dim(raw_h as usize) as u32;
                if width == 0 || height == 0 {
                    std::thread::sleep(poll_interval);
                    continue;
                }

                let pixel_len = (stride * height) as usize;
                if pixel_len > SHM_DATA_SIZE {
                    std::thread::sleep(poll_interval);
                    continue;
                }

                let pixel_copy: Vec<u8> = shm.pixel_slice(pixel_len).to_vec();

                let (seq2, ..) = shm.read_header();
                if seq2 != seq {
                    continue;
                }

                last_seq = seq;
                last_frame_time = Instant::now();

                let dims = (width, height);
                if encoder_dims != Some(dims) {
                    encoder = None;
                    encoder_dims = None;
                }

                let enc = match encoder.as_mut() {
                    Some(e) => e,
                    None => match MfH264Encoder::new(width, height, u32::from(frame_fps())) {
                        Ok(e) => {
                            encoder = Some(e);
                            encoder_dims = Some(dims);
                            encoder.as_mut().unwrap()
                        }
                        Err(e) => {
                            eprintln!("encoder init failed: {e}");
                            std::thread::sleep(Duration::from_millis(100));
                            continue;
                        }
                    },
                };

                let bytes = match enc.encode_rgba(&pixel_copy, stride as usize) {
                    Ok(b) => b,
                    Err(e) => {
                        eprintln!("encode error: {e}");
                        encoder = None;
                        encoder_dims = None;
                        continue;
                    }
                };

                if !bytes.is_empty() {
                    let _ = frame_tx.try_send(EncodedFrame {
                        data: bytes,
                        captured_at: Instant::now(),
                    });
                }
            }
        }
    })
}
