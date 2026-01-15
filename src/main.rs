//! FGP Calendar Daemon
//!
//! Fast daemon for Google Calendar operations using PyO3 for warm Python connections.
//!
//! # Architecture
//!
//! The daemon loads a Python module ONCE at startup via PyO3, keeping the
//! Calendar API connection warm. This eliminates the ~1-2s cold start overhead
//! of spawning a new Python subprocess for each request.
//!
//! Performance comparison:
//! - Subprocess per call: ~1.5s (cold Python + OAuth + API init every time)
//! - PyO3 warm connection: ~30-50ms (10-100x faster!)
//!
//! # Methods
//! - `calendar.today` - Get today's events
//! - `calendar.upcoming` - Get upcoming events (with days/limit params)
//! - `calendar.search` - Search events by query
//! - `calendar.create` - Create a new event (with location/attendees support)
//! - `calendar.get` - Get a specific event by ID
//! - `calendar.update` - Update an existing event
//! - `calendar.delete` - Delete an event
//! - `calendar.quick` - Quick add from natural language (e.g., "Meeting tomorrow at 3pm")
//! - `calendar.free_slots` - Find available time slots
//!
//! # Setup
//! 1. Place Google OAuth credentials in ~/.fgp/auth/google/credentials.json
//! 2. Run once to complete OAuth flow
//! 3. Daemon will use cached tokens for subsequent calls
//!
//! # Run
//! ```bash
//! cargo run --release
//! ```
//!
//! # Test
//! ```bash
//! fgp call calendar.today
//! fgp call calendar.upcoming -p '{"days": 7}'
//! fgp call calendar.quick -p '{"text": "Meeting with John tomorrow at 3pm"}'
//! fgp call calendar.free_slots -p '{"duration_minutes": 30}'
//! ```
//!
//! CHANGELOG (recent first, max 5 entries)
//! 01/14/2026 - Added get, delete, update, quick methods (Claude)
//! 01/13/2026 - Switched to PyO3 PythonModule for warm connections (Claude)
//! 01/12/2026 - Initial implementation with subprocess per call (Claude)

use anyhow::{bail, Context, Result};
use fgp_daemon::python::PythonModule;
use fgp_daemon::FgpServer;
use std::path::PathBuf;

/// Find the Calendar Python module.
///
/// Searches in order:
/// 1. Next to the binary: ./module/gcal.py
/// 2. FGP services directory: ~/.fgp/services/calendar/module/gcal.py
/// 3. Cargo manifest directory (development): ./module/gcal.py
fn find_module_path() -> Result<PathBuf> {
    // Check next to the binary
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let module_path = exe_dir.join("module").join("gcal.py");
            if module_path.exists() {
                return Ok(module_path);
            }
        }
    }

    // Check FGP services directory
    if let Some(home) = dirs::home_dir() {
        let module_path = home
            .join(".fgp")
            .join("services")
            .join("calendar")
            .join("module")
            .join("gcal.py");
        if module_path.exists() {
            return Ok(module_path);
        }
    }

    // Fallback to cargo manifest directory (development)
    let cargo_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("module")
        .join("gcal.py");
    if cargo_path.exists() {
        return Ok(cargo_path);
    }

    bail!(
        "Calendar module not found. Searched:\n\
         - <exe_dir>/module/gcal.py\n\
         - ~/.fgp/services/calendar/module/gcal.py\n\
         - {}/module/gcal.py",
        env!("CARGO_MANIFEST_DIR")
    )
}

fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter("fgp_calendar=debug,fgp_daemon=debug")
        .init();

    println!("Starting Calendar daemon (PyO3 warm connection)...");
    println!();

    // Find and load the Python module
    let module_path = find_module_path()?;
    println!("Loading Python module: {}", module_path.display());

    let module = PythonModule::load(&module_path, "CalendarModule")
        .context("Failed to load CalendarModule")?;

    println!("Calendar service initialized (warm connection ready)");
    println!();
    println!("Socket: ~/.fgp/services/calendar/daemon.sock");
    println!();
    println!("Available methods:");
    println!("  calendar.today              - Get today's events");
    println!("  calendar.upcoming           - Get upcoming events");
    println!("  calendar.search             - Search events by query");
    println!("  calendar.create             - Create a new event");
    println!("  calendar.get                - Get event by ID");
    println!("  calendar.update             - Update an event");
    println!("  calendar.delete             - Delete an event");
    println!("  calendar.quick              - Quick add from natural language");
    println!("  calendar.free_slots         - Find available time slots");
    println!();
    println!("Test with:");
    println!("  fgp call calendar.today");
    println!("  fgp call calendar.upcoming -p '{{\"days\": 7}}'");
    println!("  fgp call calendar.quick -p '{{\"text\": \"Meeting tomorrow at 3pm\"}}'");
    println!();

    let server = FgpServer::new(module, "~/.fgp/services/calendar/daemon.sock")?;
    server.serve()?;

    Ok(())
}
