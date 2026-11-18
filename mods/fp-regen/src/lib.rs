//! fp_regen - Mod Engine 3 native mod: slow, always-on FP (Focus) regeneration.
//!
//! Target: Elden Ring 1.17.3 (regulation.bin 1.17.2). Uses the `eldenring` crate for the
//! version-specific PlayerGameData layout, so there are no hardcoded offsets.
//!
//! Pattern follows the official eldenring-rs example (debug-line): DllMain spawns a thread,
//! waits for the game's task runner, then runs a closure every frame.
//!
//! Build: see build.ps1 (installs Rust if needed, builds, copies the DLL to dll/offline).

use std::sync::Mutex;
use std::time::{Duration, Instant};

use eldenring::cs::{CSTaskGroupIndex, CSTaskImp, PlayerIns};
use eldenring::fd4::FD4TaskData;
use fromsoftware_shared::task::SharedTaskImpExt;

/// FP restored per second. 1.0 is a slow trickle (~100s to refill a 100 FP bar).
const REGEN_PER_SEC: f32 = 1.0;

/// Last frame time + fractional accumulator (the game task runs every frame; we integrate dt).
static LAST: Mutex<Option<Instant>> = Mutex::new(None);
static ACC: Mutex<f32> = Mutex::new(0.0);

#[unsafe(no_mangle)]
/// # Safety
/// Exported so Windows' LoadLibrary can call it on DLL_PROCESS_ATTACH. Do not call it yourself.
pub unsafe extern "C" fn DllMain(_hmodule: usize, reason: u32) -> bool {
    if reason != 1 {
        return true; // only act on DLL_PROCESS_ATTACH
    }
    std::thread::spawn(|| {
        // Wait for the game to boot and its task runner to exist.
        let Ok(cs_task) = CSTaskImp::wait_for_instance(Duration::MAX) else {
            return;
        };
        // Run every frame, after physics (same phase the official example uses).
        cs_task.run_recurring(|_: &FD4TaskData| tick(), CSTaskGroupIndex::ChrIns_PostPhysics);
    });
    true
}

fn tick() {
    let now = Instant::now();
    let dt = {
        let mut last = LAST.lock().unwrap();
        let d = last.map(|t| now.duration_since(t).as_secs_f32()).unwrap_or(0.0);
        *last = Some(now);
        d
    };
    if dt <= 0.0 || dt > 0.25 {
        return; // ignore load pauses / huge frames
    }

    let mut acc = ACC.lock().unwrap();
    *acc += REGEN_PER_SEC * dt;
    let whole = *acc as u32;
    if whole == 0 {
        return;
    }
    *acc -= whole as f32;
    drop(acc);

    // Only the local player, only while alive, only up to max FP.
    if let Ok(player) = unsafe { PlayerIns::local_player() } {
        let mut nn = player.player_game_data;
        let gd = unsafe { nn.as_mut() };
        if gd.current_hp > 0 && gd.current_fp < gd.current_max_fp {
            gd.current_fp = (gd.current_fp + whole).min(gd.current_max_fp);
        }
    }
}