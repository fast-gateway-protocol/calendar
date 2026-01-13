//! FGP Calendar Daemon
//!
//! Fast daemon for Google Calendar operations. Uses a Python CLI helper for Calendar API calls.
//!
//! # Methods
//! - `today` - Get today's events
//! - `upcoming` - Get upcoming events
//! - `search` - Search events by query
//! - `create` - Create a new event
//! - `free_slots` - Find available time slots
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
//! fgp call calendar.free_slots -p '{"duration_minutes": 30}'
//! ```

use anyhow::{bail, Context, Result};
use fgp_daemon::service::{HealthStatus, MethodInfo, ParamInfo};
use fgp_daemon::{FgpServer, FgpService};
use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Command;

/// Path to the Calendar CLI helper script.
fn calendar_cli_path() -> PathBuf {
    // First check next to the binary
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()));

    if let Some(dir) = exe_dir {
        let script = dir.join("calendar-cli.py");
        if script.exists() {
            return script;
        }
        // Check in scripts/ relative to binary
        let script = dir.join("scripts").join("calendar-cli.py");
        if script.exists() {
            return script;
        }
    }

    // Check ~/.fgp/services/calendar/calendar-cli.py
    if let Some(home) = dirs::home_dir() {
        let script = home.join(".fgp/services/calendar/calendar-cli.py");
        if script.exists() {
            return script;
        }
    }

    // Fallback - assume it's in the cargo project
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("scripts/calendar-cli.py")
}

/// Calendar service using Python CLI for API calls.
struct CalendarService {
    cli_path: PathBuf,
}

impl CalendarService {
    fn new() -> Result<Self> {
        let cli_path = calendar_cli_path();
        if !cli_path.exists() {
            bail!(
                "Calendar CLI not found at: {}\nEnsure calendar-cli.py is installed.",
                cli_path.display()
            );
        }
        Ok(Self { cli_path })
    }

    /// Run the Calendar CLI helper and parse JSON output.
    fn run_cli(&self, args: &[&str]) -> Result<Value> {
        let output = Command::new("python3")
            .arg(&self.cli_path)
            .args(args)
            .output()
            .context("Failed to run calendar-cli.py")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            // Try to parse JSON error from stdout
            if let Ok(error_json) = serde_json::from_slice::<Value>(&output.stdout) {
                if let Some(error) = error_json.get("error").and_then(|e| e.as_str()) {
                    bail!("Calendar API error: {}", error);
                }
            }
            bail!("calendar-cli failed: {}", stderr);
        }

        serde_json::from_slice(&output.stdout).context("Failed to parse calendar-cli output")
    }
}

impl FgpService for CalendarService {
    fn name(&self) -> &str {
        "calendar"
    }

    fn version(&self) -> &str {
        "1.0.0"
    }

    fn dispatch(&self, method: &str, params: HashMap<String, Value>) -> Result<Value> {
        match method {
            "calendar.today" => self.today(),
            "calendar.upcoming" => self.upcoming(params),
            "calendar.search" => self.search(params),
            "calendar.create" => self.create(params),
            "calendar.free_slots" => self.free_slots(params),
            _ => bail!("Unknown method: {}", method),
        }
    }

    fn method_list(&self) -> Vec<MethodInfo> {
        vec![
            MethodInfo {
                name: "calendar.today".into(),
                description: "Get today's calendar events".into(),
                params: vec![],
            },
            MethodInfo {
                name: "calendar.upcoming".into(),
                description: "Get upcoming events".into(),
                params: vec![
                    ParamInfo {
                        name: "days".into(),
                        param_type: "integer".into(),
                        required: false,
                        default: Some(Value::Number(7.into())),
                    },
                    ParamInfo {
                        name: "limit".into(),
                        param_type: "integer".into(),
                        required: false,
                        default: Some(Value::Number(20.into())),
                    },
                ],
            },
            MethodInfo {
                name: "calendar.search".into(),
                description: "Search events by query".into(),
                params: vec![
                    ParamInfo {
                        name: "query".into(),
                        param_type: "string".into(),
                        required: true,
                        default: None,
                    },
                    ParamInfo {
                        name: "days".into(),
                        param_type: "integer".into(),
                        required: false,
                        default: Some(Value::Number(30.into())),
                    },
                ],
            },
            MethodInfo {
                name: "calendar.create".into(),
                description: "Create a new event".into(),
                params: vec![
                    ParamInfo {
                        name: "summary".into(),
                        param_type: "string".into(),
                        required: true,
                        default: None,
                    },
                    ParamInfo {
                        name: "start".into(),
                        param_type: "string".into(),
                        required: true,
                        default: None,
                    },
                    ParamInfo {
                        name: "end".into(),
                        param_type: "string".into(),
                        required: true,
                        default: None,
                    },
                    ParamInfo {
                        name: "description".into(),
                        param_type: "string".into(),
                        required: false,
                        default: None,
                    },
                ],
            },
            MethodInfo {
                name: "calendar.free_slots".into(),
                description: "Find available time slots".into(),
                params: vec![
                    ParamInfo {
                        name: "duration_minutes".into(),
                        param_type: "integer".into(),
                        required: true,
                        default: None,
                    },
                    ParamInfo {
                        name: "days".into(),
                        param_type: "integer".into(),
                        required: false,
                        default: Some(Value::Number(7.into())),
                    },
                ],
            },
        ]
    }

    fn on_start(&self) -> Result<()> {
        // Verify Calendar CLI exists and Python is available
        let output = Command::new("python3")
            .arg("--version")
            .output()
            .context("Python3 not found")?;

        if !output.status.success() {
            bail!("Python3 not available");
        }

        tracing::info!(
            cli_path = %self.cli_path.display(),
            "Calendar daemon starting"
        );
        Ok(())
    }

    fn health_check(&self) -> HashMap<String, HealthStatus> {
        let mut status = HashMap::new();

        // Check if CLI exists
        if self.cli_path.exists() {
            status.insert(
                "calendar_cli".into(),
                HealthStatus {
                    ok: true,
                    latency_ms: None,
                    message: Some(format!("CLI at {}", self.cli_path.display())),
                },
            );
        } else {
            status.insert(
                "calendar_cli".into(),
                HealthStatus {
                    ok: false,
                    latency_ms: None,
                    message: Some("calendar-cli.py not found".into()),
                },
            );
        }

        status
    }
}

impl CalendarService {
    /// Get today's events.
    fn today(&self) -> Result<Value> {
        self.run_cli(&["today"])
    }

    /// Get upcoming events.
    fn upcoming(&self, params: HashMap<String, Value>) -> Result<Value> {
        let days = params
            .get("days")
            .and_then(|v| v.as_u64())
            .unwrap_or(7);

        let limit = params
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20);

        self.run_cli(&["upcoming", "--days", &days.to_string(), "--limit", &limit.to_string()])
    }

    /// Search events.
    fn search(&self, params: HashMap<String, Value>) -> Result<Value> {
        let query = params
            .get("query")
            .and_then(|v| v.as_str())
            .context("query parameter is required")?;

        let days = params
            .get("days")
            .and_then(|v| v.as_u64())
            .unwrap_or(30);

        self.run_cli(&["search", query, "--days", &days.to_string()])
    }

    /// Create a new event.
    fn create(&self, params: HashMap<String, Value>) -> Result<Value> {
        let summary = params
            .get("summary")
            .and_then(|v| v.as_str())
            .context("summary parameter is required")?;

        let start = params
            .get("start")
            .and_then(|v| v.as_str())
            .context("start parameter is required")?;

        let end = params
            .get("end")
            .and_then(|v| v.as_str())
            .context("end parameter is required")?;

        let mut args = vec!["create", summary, start, end];

        let description;
        if let Some(desc) = params.get("description").and_then(|v| v.as_str()) {
            description = desc.to_string();
            args.push("--description");
            args.push(&description);
        }

        self.run_cli(&args)
    }

    /// Find free time slots.
    fn free_slots(&self, params: HashMap<String, Value>) -> Result<Value> {
        let duration = params
            .get("duration_minutes")
            .and_then(|v| v.as_u64())
            .context("duration_minutes parameter is required")?;

        let days = params
            .get("days")
            .and_then(|v| v.as_u64())
            .unwrap_or(7);

        self.run_cli(&["free-slots", "--duration", &duration.to_string(), "--days", &days.to_string()])
    }
}

fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter("fgp_calendar=debug,fgp_daemon=debug")
        .init();

    println!("Starting Calendar daemon...");
    println!("Socket: ~/.fgp/services/calendar/daemon.sock");
    println!();
    println!("Test with:");
    println!("  fgp call calendar.today");
    println!("  fgp call calendar.upcoming -p '{{\"days\": 7}}'");
    println!("  fgp call calendar.free_slots -p '{{\"duration_minutes\": 30}}'");
    println!();

    let service = CalendarService::new()?;
    let server = FgpServer::new(service, "~/.fgp/services/calendar/daemon.sock")?;
    server.serve()?;

    Ok(())
}
