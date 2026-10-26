#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use std::env;
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

const DEFAULT_PORT: u16 = 24820;

fn is_port_listening(port: u16) -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

fn find_repo_root() -> PathBuf {
    if let Ok(exe_path) = env::current_exe() {
        let mut cur: Option<&Path> = exe_path.parent();
        while let Some(dir) = cur {
            if dir.join("src").join("python").join("quick_expense_server.py").exists() {
                return dir.to_path_buf();
            }
            cur = dir.parent();
        }
    }
    if let Ok(cwd) = env::current_dir() {
        let mut cur: Option<&Path> = Some(cwd.as_path());
        while let Some(dir) = cur {
            if dir.join("src").join("python").join("quick_expense_server.py").exists() {
                return dir.to_path_buf();
            }
            cur = dir.parent();
        }
    }
    PathBuf::from(".")
}

fn find_python_executable(repo_root: &Path) -> PathBuf {
    if let Ok(entries) = std::fs::read_dir(repo_root) {
        for entry in entries.flatten() {
            let path = entry.path();
            if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                if name.starts_with(".venv") && path.is_dir() {
                    #[cfg(target_os = "windows")]
                    {
                        let pyw = path.join("Scripts").join("pythonw.exe");
                        if pyw.exists() {
                            return pyw;
                        }
                        let py = path.join("Scripts").join("python.exe");
                        if py.exists() {
                            return py;
                        }
                    }
                    #[cfg(not(target_os = "windows"))]
                    {
                        let py = path.join("bin").join("python3");
                        if py.exists() {
                            return py;
                        }
                    }
                }
            }
        }
    }
    #[cfg(target_os = "windows")]
    {
        PathBuf::from("pythonw.exe")
    }
    #[cfg(not(target_os = "windows"))]
    {
        PathBuf::from("python3")
    }
}

fn ensure_server_running(repo_root: &Path, port: u16) {
    if is_port_listening(port) {
        return;
    }
    let py_exe = find_python_executable(repo_root);
    let server_script = repo_root.join("src").join("python").join("quick_expense_server.py");

    let mut cmd = Command::new(py_exe);
    cmd.current_dir(repo_root)
        .arg(&server_script)
        .arg("--port")
        .arg(port.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    let _ = cmd.spawn();

    for _ in 0..25 {
        if is_port_listening(port) {
            break;
        }
        thread::sleep(Duration::from_millis(120));
    }
}

fn open_dialog_window(url: &str) {
    #[cfg(target_os = "windows")]
    {
        let candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ];
        for cand in candidates {
            let p = Path::new(cand);
            if p.exists() {
                let mut cmd = Command::new(p);
                cmd.arg(format!("--app={}", url))
                    .arg("--window-size=820,860")
                    .stdin(Stdio::null())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .creation_flags(CREATE_NO_WINDOW);
                if cmd.spawn().is_ok() {
                    return;
                }
            }
        }
        let mut fallback = Command::new("cmd.exe");
        fallback
            .args(["/C", "start", "", url])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW);
        let _ = fallback.spawn();
    }

    #[cfg(target_os = "linux")]
    {
        let candidates = ["google-chrome", "chromium-browser", "chromium", "xdg-open"];
        for bin in candidates {
            let mut cmd = Command::new(bin);
            if bin != "xdg-open" {
                cmd.arg(format!("--app={}", url)).arg("--window-size=820,860");
            } else {
                cmd.arg(url);
            }
            cmd.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
            if cmd.spawn().is_ok() {
                return;
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        let chrome = Path::new("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
        if chrome.exists() {
            let mut cmd = Command::new(chrome);
            cmd.arg(format!("--app={}", url))
                .arg("--window-size=820,860")
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            if cmd.spawn().is_ok() {
                return;
            }
        }
        let _ = Command::new("open").arg(url).spawn();
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut user_arg = String::new();
    let mut headless_only = false;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--user" if i + 1 < args.len() => {
                user_arg = args[i + 1].clone();
                i += 1;
            }
            "--server-only" => {
                headless_only = true;
            }
            _ => {}
        }
        i += 1;
    }

    let repo_root = find_repo_root();
    ensure_server_running(&repo_root, DEFAULT_PORT);

    if !headless_only {
        let url = if user_arg.is_empty() {
            format!("http://127.0.0.1:{}", DEFAULT_PORT)
        } else {
            format!("http://127.0.0.1:{}/?user={}", DEFAULT_PORT, user_arg)
        };
        open_dialog_window(&url);
    }
}
