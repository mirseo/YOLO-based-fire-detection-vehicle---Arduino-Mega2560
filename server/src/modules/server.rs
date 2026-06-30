use anyhow::Result;
use tokio::net::{TcpListener, TcpStream};

use crate::modules::config::BIND_ADDR;
use crate::modules::control::forward_control;
use crate::modules::session::handle_peer;

pub async fn run() -> Result<()> {
    let listener = TcpListener::bind(BIND_ADDR).await?;
    println!("streaming server listening on http+ws://{BIND_ADDR}");
    install_shutdown_handler();
    loop {
        let (stream, _) = listener.accept().await?;
        tokio::spawn(async move {
            if let Err(e) = route(stream).await {
                eprintln!("peer error: {e}");
            }
        });
    }
}

async fn route(stream: TcpStream) -> Result<()> {
    if peek_is_control(&stream).await? {
        forward_control(stream).await
    } else {
        handle_peer(stream).await
    }
}

async fn peek_is_control(stream: &TcpStream) -> Result<bool> {
    let mut buf = [0u8; 32];
    let n = stream.peek(&mut buf).await?;
    Ok(buf[..n].starts_with(b"POST /api/control"))
}

fn install_shutdown_handler() {
    tokio::spawn(async {
        let _ = tokio::signal::ctrl_c().await;
        println!("shutting down");
        std::process::exit(0);
    });
}
