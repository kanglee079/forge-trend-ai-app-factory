import { app, BrowserWindow, dialog, shell } from "electron";

const dashboardUrl = process.env.FORGE_DASHBOARD_URL ?? "http://localhost:3000";

async function createWindow() {
  const window = new BrowserWindow({
    width: 1320,
    height: 880,
    minWidth: 1024,
    minHeight: 720,
    title: "ForgeTrend AI App Factory",
    backgroundColor: "#f5f8f8",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  try {
    await window.loadURL(dashboardUrl);
  } catch {
    await window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(renderOfflinePage())}`);
  }
}

function renderOfflinePage() {
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>ForgeTrend</title>
    <style>
      body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f8f8; color: #172026; }
      main { min-height: 100vh; display: grid; place-items: center; padding: 32px; }
      section { max-width: 560px; border: 1px solid #cbd8d8; background: white; border-radius: 8px; padding: 28px; box-shadow: 0 8px 24px rgba(23, 32, 38, 0.08); }
      h1 { margin: 0 0 12px; font-size: 24px; }
      p { line-height: 1.55; color: #526166; }
      code { background: #edf3f3; border-radius: 4px; padding: 2px 5px; }
    </style>
  </head>
  <body>
    <main>
      <section>
        <h1>ForgeTrend is not running yet</h1>
        <p>Start the app with <code>./run.command</code> on macOS or <code>run.bat</code> on Windows. The launcher starts the local services and opens this desktop window.</p>
      </section>
    </main>
  </body>
</html>`;
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow().catch((error) => {
      dialog.showErrorBox("ForgeTrend", String(error));
    });
  }
});
