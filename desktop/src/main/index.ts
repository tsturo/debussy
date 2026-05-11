import { app, BrowserWindow, shell, nativeImage } from 'electron'
import { join } from 'path'
import { registerIPC } from './ipc-register'

// Use the renderer URL set by electron-vite dev server when available;
// fall back to loading the built renderer file (covers both E2E tests and packaged apps).
const isDev = !!process.env['ELECTRON_RENDERER_URL']

// Single-instance lock: quit if another instance is already running.
let mainWindow: BrowserWindow | null = null

const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    // Focus existing window when a second instance is launched.
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })
}

// Resolve icon: prefer .icns on macOS for best quality, fall back to PNG.
function resolveIcon(): string {
  if (process.platform === 'darwin') {
    return join(__dirname, '../../build/icon.icns')
  }
  return join(__dirname, '../../build/icon.png')
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'Debussy',
    show: false,
    icon: resolveIcon(),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow!.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (isDev) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'] ?? 'http://localhost:5173')
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  app.setName('Debussy')
  registerIPC()

  // Set macOS dock icon explicitly (dev mode doesn't pick it up from the bundle).
  if (process.platform === 'darwin') {
    const dockIcon = nativeImage.createFromPath(join(__dirname, '../../build/icon.png'))
    app.dock.setIcon(dockIcon)
  }

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
