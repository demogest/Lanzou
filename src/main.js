import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import "./styles.css";

const app = document.querySelector("#app");

app.innerHTML = `
  <div class="shell">
    <header class="app-header">
      <div>
        <h1>蓝奏云下载器</h1>
        <p>粘贴分享链接，选择保存目录，批量下载同一分享页内的文件。</p>
      </div>
      <div class="header-actions">
        <button class="secondary" id="settingsBtn" type="button">下载设置</button>
        <button class="secondary" id="historyBtn" type="button">下载历史</button>
      </div>
    </header>

    <main class="workspace">
      <section class="panel input-panel">
        <div class="field">
          <label for="shareUrl">分享链接</label>
          <input id="shareUrl" autocomplete="off" placeholder="粘贴蓝奏云分享链接" />
        </div>
        <div class="field">
          <label for="password">提取码</label>
          <input id="password" autocomplete="off" placeholder="没有提取码可留空" />
        </div>
        <div class="field">
          <label for="targetDir">保存位置</label>
          <div class="inline-field">
            <input id="targetDir" autocomplete="off" placeholder="选择下载保存目录" />
            <button class="secondary" id="chooseDirBtn" type="button">选择目录</button>
          </div>
        </div>
        <div class="form-footer">
          <span id="processHint">并发进程：1</span>
          <button class="primary" id="startBtn" type="button">开始下载</button>
        </div>
      </section>

      <section class="panel progress-panel">
        <div class="section-heading">
          <div>
            <h2>任务进度</h2>
            <p id="statusText">等待任务</p>
          </div>
          <strong id="totalPercent">0%</strong>
        </div>
        <div class="progress-track" aria-label="总进度">
          <div id="totalProgress" class="progress-fill"></div>
        </div>
        <div id="processList" class="process-list"></div>
      </section>

      <section class="panel log-panel">
        <div class="section-heading compact">
          <h2>下载日志</h2>
          <button class="ghost" id="clearLogBtn" type="button">清空</button>
        </div>
        <div class="log-table">
          <div class="log-row log-head">
            <span>阶段</span>
            <span>序号</span>
            <span>消息</span>
          </div>
          <div id="logRows"></div>
        </div>
      </section>
    </main>

    <dialog id="settingsDialog" class="dialog">
      <form method="dialog">
        <header>
          <h2>下载设置</h2>
          <button class="icon-button" value="cancel" aria-label="关闭" type="submit">×</button>
        </header>
        <div class="dialog-body">
          <div class="field">
            <label for="defaultDir">默认目录</label>
            <div class="inline-field">
              <input id="defaultDir" autocomplete="off" />
              <button class="secondary" id="chooseDefaultDirBtn" type="button">选择目录</button>
            </div>
          </div>
          <div class="field">
            <label for="processCount">下载进程</label>
            <input id="processCount" type="number" min="1" step="1" />
          </div>
        </div>
        <footer>
          <button class="secondary" value="cancel" type="submit">取消</button>
          <button class="primary" id="saveSettingsBtn" type="button">保存</button>
        </footer>
      </form>
    </dialog>

    <dialog id="historyDialog" class="dialog history-dialog">
      <form method="dialog">
        <header>
          <h2>下载历史</h2>
          <button class="icon-button" value="cancel" aria-label="关闭" type="submit">×</button>
        </header>
        <div class="history-layout">
          <div class="history-list-wrap">
            <div id="historyList" class="history-list"></div>
            <div class="history-actions">
              <button class="secondary" id="deleteHistoryBtn" type="button">删除选中</button>
              <button class="danger" id="clearHistoryBtn" type="button">清空历史</button>
            </div>
          </div>
          <pre id="historyDetails" class="history-details">暂无下载记录。</pre>
        </div>
      </form>
    </dialog>

    <dialog id="completeDialog" class="dialog small-dialog">
      <form method="dialog">
        <header>
          <h2>下载完成</h2>
          <button class="icon-button" value="cancel" aria-label="关闭" type="submit">×</button>
        </header>
        <p id="completeText">任务已完成。</p>
        <footer>
          <button class="secondary" value="cancel" type="submit">关闭</button>
          <button class="primary" id="openFolderBtn" type="button">打开文件夹</button>
        </footer>
      </form>
    </dialog>
  </div>
`;

const elements = {
  shareUrl: document.querySelector("#shareUrl"),
  password: document.querySelector("#password"),
  targetDir: document.querySelector("#targetDir"),
  chooseDirBtn: document.querySelector("#chooseDirBtn"),
  startBtn: document.querySelector("#startBtn"),
  processHint: document.querySelector("#processHint"),
  statusText: document.querySelector("#statusText"),
  totalPercent: document.querySelector("#totalPercent"),
  totalProgress: document.querySelector("#totalProgress"),
  processList: document.querySelector("#processList"),
  logRows: document.querySelector("#logRows"),
  clearLogBtn: document.querySelector("#clearLogBtn"),
  settingsBtn: document.querySelector("#settingsBtn"),
  historyBtn: document.querySelector("#historyBtn"),
  settingsDialog: document.querySelector("#settingsDialog"),
  historyDialog: document.querySelector("#historyDialog"),
  completeDialog: document.querySelector("#completeDialog"),
  defaultDir: document.querySelector("#defaultDir"),
  chooseDefaultDirBtn: document.querySelector("#chooseDefaultDirBtn"),
  processCount: document.querySelector("#processCount"),
  saveSettingsBtn: document.querySelector("#saveSettingsBtn"),
  historyList: document.querySelector("#historyList"),
  historyDetails: document.querySelector("#historyDetails"),
  deleteHistoryBtn: document.querySelector("#deleteHistoryBtn"),
  clearHistoryBtn: document.querySelector("#clearHistoryBtn"),
  completeText: document.querySelector("#completeText"),
  openFolderBtn: document.querySelector("#openFolderBtn"),
};

const state = {
  settings: {
    defaultDownloadDir: "",
    processCount: 1,
  },
  maxProcesses: 1,
  history: [],
  selectedHistoryIndex: 0,
  downloading: false,
  logSeq: 0,
};

function setTotalProgress(progress) {
  const value = Math.max(0, Math.min(100, Number(progress) || 0));
  elements.totalPercent.textContent = `${value}%`;
  elements.totalProgress.style.width = `${value}%`;
}

function renderProcessRows(count) {
  const rows = [];
  for (let slot = 1; slot <= count; slot += 1) {
    rows.push(`
      <div class="process-row" data-slot="${slot}">
        <span class="slot">进程 ${slot}</span>
        <span class="file" title="">等待任务</span>
        <div class="mini-progress"><span style="width: 0%"></span></div>
        <span class="process-status">等待</span>
      </div>
    `);
  }
  elements.processList.innerHTML = rows.join("");
}

function updateProcessProgress(slot, fileName, progress, status) {
  const row = elements.processList.querySelector(`[data-slot="${slot}"]`);
  if (!row) return;
  const value = Math.max(0, Math.min(100, Number(progress) || 0));
  const displayName = fileName || "等待任务";
  row.querySelector(".file").textContent = displayName;
  row.querySelector(".file").title = fileName || "";
  row.querySelector(".mini-progress span").style.width = `${value}%`;
  row.querySelector(".process-status").textContent = status || "下载中";
}

function classifyLog(message) {
  const lower = String(message).toLowerCase();
  if (lower.includes("error") || message.includes("失败")) return "错误";
  if (message.includes("解析") || message.includes("提取") || lower.includes("resolving")) return "解析";
  if (message.includes("完成") || lower.includes("finished")) return "完成";
  return "下载";
}

function addLog(message) {
  state.logSeq += 1;
  const row = document.createElement("div");
  row.className = "log-row";
  row.innerHTML = `
    <span>${classifyLog(message)}</span>
    <span>${state.logSeq}</span>
    <span></span>
  `;
  row.lastElementChild.textContent = String(message);
  elements.logRows.append(row);
  row.scrollIntoView({ block: "nearest" });
}

function clearLog() {
  state.logSeq = 0;
  elements.logRows.innerHTML = "";
}

function setDownloading(isDownloading) {
  state.downloading = isDownloading;
  elements.startBtn.disabled = isDownloading;
  elements.chooseDirBtn.disabled = isDownloading;
  elements.settingsBtn.disabled = isDownloading;
  elements.startBtn.textContent = isDownloading ? "下载中..." : "开始下载";
  elements.statusText.textContent = isDownloading ? "任务运行中" : "等待任务";
}

function applySettings(settings, maxProcesses = state.maxProcesses) {
  state.settings = {
    defaultDownloadDir: settings.defaultDownloadDir || "",
    processCount: Math.max(1, Number(settings.processCount) || 1),
  };
  state.maxProcesses = Math.max(1, Number(maxProcesses) || 1);
  elements.targetDir.value ||= state.settings.defaultDownloadDir;
  elements.defaultDir.value = state.settings.defaultDownloadDir;
  elements.processCount.max = String(state.maxProcesses);
  elements.processCount.value = String(Math.min(state.settings.processCount, state.maxProcesses));
  elements.processHint.textContent = `并发进程：${state.settings.processCount}`;
  renderProcessRows(state.settings.processCount);
}

async function chooseDirectory(currentDir) {
  const selected = await invoke("choose_directory", { currentDir });
  return selected || "";
}

async function startDownload() {
  const shareUrl = elements.shareUrl.value.trim();
  if (!shareUrl) {
    addLog("请先输入蓝奏云分享链接。");
    elements.shareUrl.focus();
    return;
  }

  const targetDir = elements.targetDir.value.trim() || state.settings.defaultDownloadDir;
  if (!targetDir) {
    addLog("请先选择下载保存目录。");
    return;
  }

  elements.targetDir.value = targetDir;
  clearLog();
  setTotalProgress(0);
  renderProcessRows(state.settings.processCount);
  setDownloading(true);
  addLog("Getting file list...");

  try {
    const files = await invoke("start_download", {
      task: {
        shareUrl,
        password: elements.password.value,
        targetDir,
        processCount: state.settings.processCount,
      },
    });
    setTotalProgress(100);
    elements.statusText.textContent = "下载完成";
    elements.completeText.textContent = `任务已完成，成功处理 ${files.length} 个文件。`;
    elements.completeDialog.showModal();
    state.history = await invoke("load_history");
  } catch (error) {
    addLog(`Error: ${error}`);
    elements.statusText.textContent = "任务失败";
  } finally {
    setDownloading(false);
  }
}

function renderHistory() {
  elements.historyList.innerHTML = "";
  if (!state.history.length) {
    elements.historyList.innerHTML = `<div class="empty-state">暂无下载历史</div>`;
    elements.historyDetails.textContent = "暂无下载记录。";
    elements.deleteHistoryBtn.disabled = true;
    elements.clearHistoryBtn.disabled = true;
    return;
  }

  elements.deleteHistoryBtn.disabled = false;
  elements.clearHistoryBtn.disabled = false;
  state.history.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `history-item ${index === state.selectedHistoryIndex ? "active" : ""}`;
    button.innerHTML = `
      <strong>${item.time || "-"}</strong>
      <span>${item.downloadedCount || 0} 个文件 · 进程 ${item.processCount || 1}</span>
    `;
    button.addEventListener("click", () => {
      state.selectedHistoryIndex = index;
      renderHistory();
    });
    elements.historyList.append(button);
  });
  renderHistoryDetails();
}

function renderHistoryDetails() {
  const record = state.history[state.selectedHistoryIndex];
  if (!record) {
    elements.historyDetails.textContent = "暂无下载记录。";
    return;
  }

  const files = (record.files || [])
    .map((file, index) => `${index + 1}. ${file.name || ""} | ${file.size || "未知"}\n   ${file.path || ""}`)
    .join("\n");

  elements.historyDetails.textContent =
    `时间：${record.time || "-"}\n` +
    `URL：${record.shareUrl || "-"}\n` +
    `密码：${record.password || "（无）"}\n` +
    `完成时间：${record.finishedTime || record.time || "-"}\n` +
    `保存目录：${record.targetDir || "-"}\n` +
    `并发进程：${record.processCount || 1}\n` +
    `下载文件数：${record.downloadedCount || 0}\n\n` +
    `下载文件信息：\n${files || "无"}`;
}

async function init() {
  const initial = await invoke("initial_state");
  state.history = initial.history || [];
  applySettings(initial, initial.maxProcesses);

  await listen("download-event", (event) => {
    const payload = event.payload;
    if (!payload) return;
    if (payload.type === "message") addLog(payload.message);
    if (payload.type === "totalProgress") setTotalProgress(payload.progress);
    if (payload.type === "processProgress") {
      updateProcessProgress(payload.slot, payload.fileName, payload.progress, payload.status);
    }
  });
}

elements.chooseDirBtn.addEventListener("click", async () => {
  const selected = await chooseDirectory(elements.targetDir.value || state.settings.defaultDownloadDir);
  if (selected) elements.targetDir.value = selected;
});

elements.startBtn.addEventListener("click", startDownload);
elements.clearLogBtn.addEventListener("click", clearLog);

elements.settingsBtn.addEventListener("click", () => {
  elements.defaultDir.value = state.settings.defaultDownloadDir;
  elements.processCount.value = String(state.settings.processCount);
  elements.settingsDialog.showModal();
});

elements.chooseDefaultDirBtn.addEventListener("click", async () => {
  const selected = await chooseDirectory(elements.defaultDir.value);
  if (selected) elements.defaultDir.value = selected;
});

elements.saveSettingsBtn.addEventListener("click", async () => {
  const settings = await invoke("save_settings", {
    settings: {
      defaultDownloadDir: elements.defaultDir.value.trim(),
      processCount: Number(elements.processCount.value) || 1,
    },
  });
  applySettings(settings);
  elements.settingsDialog.close();
  addLog("设置已保存。");
});

elements.historyBtn.addEventListener("click", async () => {
  state.history = await invoke("load_history");
  state.selectedHistoryIndex = 0;
  renderHistory();
  elements.historyDialog.showModal();
});

elements.deleteHistoryBtn.addEventListener("click", async () => {
  state.history = await invoke("delete_history", { index: state.selectedHistoryIndex });
  state.selectedHistoryIndex = Math.min(state.selectedHistoryIndex, Math.max(0, state.history.length - 1));
  renderHistory();
});

elements.clearHistoryBtn.addEventListener("click", async () => {
  state.history = await invoke("clear_history");
  state.selectedHistoryIndex = 0;
  renderHistory();
});

elements.openFolderBtn.addEventListener("click", async () => {
  const folder = elements.targetDir.value.trim() || state.settings.defaultDownloadDir;
  if (folder) await invoke("open_folder", { path: folder });
  elements.completeDialog.close();
});

init().catch((error) => {
  addLog(`Error: ${error}`);
});
