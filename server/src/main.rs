mod modules;

use anyhow::Result;

use crate::modules::server::run;

#[tokio::main]
async fn main() -> Result<()> {
    run().await
}
