use anyhow::Result;
use tokio::net::TcpStream;

use crate::modules::config::UPSTREAM_ADDR;

pub async fn forward_control(mut client: TcpStream) -> Result<()> {
    let mut upstream = TcpStream::connect(UPSTREAM_ADDR).await?;
    let _ = tokio::io::copy_bidirectional(&mut client, &mut upstream).await;
    Ok(())
}
