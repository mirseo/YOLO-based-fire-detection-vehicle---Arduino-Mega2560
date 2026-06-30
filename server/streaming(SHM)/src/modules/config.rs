use std::sync::OnceLock;

pub const BIND_ADDR: &str = "0.0.0.0:9000";
pub const UPSTREAM_ADDR: &str = "127.0.0.1:9001";
pub const TARGET_BITRATE_BPS: u32 = 6_000_000;
pub const FRAME_CHANNEL_CAPACITY: usize = 2;
const DEFAULT_FRAME_FPS: u16 = 30;

pub fn frame_fps() -> u16 {
    static CACHED: OnceLock<u16> = OnceLock::new();
    *CACHED.get_or_init(|| {
        std::env::var("STREAM_FPS")
            .ok()
            .and_then(|v| v.parse::<u16>().ok())
            .filter(|&v| v > 0)
            .unwrap_or(DEFAULT_FRAME_FPS)
    })
}
