import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import AppHeader from "./components/AppHeader.jsx";
import CompleteDialog from "./components/CompleteDialog.jsx";
import DownloadForm from "./components/DownloadForm.jsx";
import HistoryDialog from "./components/HistoryDialog.jsx";
import LogPanel from "./components/LogPanel.jsx";
import ProgressPanel from "./components/ProgressPanel.jsx";
import SettingsDialog from "./components/SettingsDialog.jsx";
import { Shell, Workspace } from "./components/ui.jsx";
import {
  clampProgress,
  classifyLog,
  createProcessRows,
  defaultSettings,
  formatHistoryDetails,
} from "./lib/downloadState.js";

export default function App() {
  const [shareUrl, setShareUrl] = useState("");
  const [password, setPassword] = useState("");
  const [targetDir, setTargetDir] = useState("");
  const [settings, setSettings] = useState(defaultSettings);
  const [settingsForm, setSettingsForm] = useState(defaultSettings);
  const [maxProcesses, setMaxProcesses] = useState(1);
  const [history, setHistory] = useState([]);
  const [selectedHistoryIndex, setSelectedHistoryIndex] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [logs, setLogs] = useState([]);
  const [processRows, setProcessRows] = useState(createProcessRows(1));
  const [statusText, setStatusText] = useState("等待任务");
  const [totalProgress, setTotalProgress] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [completeText, setCompleteText] = useState("任务已完成。");

  const shareUrlRef = useRef(null);
  const logSeqRef = useRef(0);
  const maxProcessesRef = useRef(1);

  const addLog = useCallback((message) => {
    const text = String(message);
    logSeqRef.current += 1;
    setLogs((current) => [
      ...current,
      {
        id: `${Date.now()}-${logSeqRef.current}`,
        message: text,
        seq: logSeqRef.current,
        type: classifyLog(text),
      },
    ]);
  }, []);

  const clearLog = useCallback(() => {
    logSeqRef.current = 0;
    setLogs([]);
  }, []);

  const applySettings = useCallback((nextSettings, nextMaxProcesses = maxProcessesRef.current) => {
    const normalized = {
      defaultDownloadDir: nextSettings?.defaultDownloadDir || "",
      processCount: Math.max(1, Number(nextSettings?.processCount) || 1),
    };
    const normalizedMax = Math.max(1, Number(nextMaxProcesses) || 1);

    maxProcessesRef.current = normalizedMax;
    setSettings(normalized);
    setSettingsForm(normalized);
    setMaxProcesses(normalizedMax);
    setTargetDir((current) => current || normalized.defaultDownloadDir);
    setProcessRows(createProcessRows(normalized.processCount));
  }, []);

  const updateProcessProgress = useCallback((slot, fileName, progress, status) => {
    setProcessRows((currentRows) =>
      currentRows.map((row) =>
        row.slot === slot
          ? {
              ...row,
              fileName: fileName || "",
              progress: clampProgress(progress),
              status: status || "下载中",
            }
          : row,
      ),
    );
  }, []);

  const chooseDirectory = useCallback(async (currentDir) => {
    const selected = await invoke("choose_directory", { currentDir });
    return selected || "";
  }, []);

  const chooseTargetDirectory = useCallback(async () => {
    const selected = await chooseDirectory(targetDir || settings.defaultDownloadDir);
    if (selected) setTargetDir(selected);
  }, [chooseDirectory, settings.defaultDownloadDir, targetDir]);

  const chooseDefaultDirectory = useCallback(async () => {
    const selected = await chooseDirectory(settingsForm.defaultDownloadDir);
    if (selected) {
      setSettingsForm((current) => ({ ...current, defaultDownloadDir: selected }));
    }
  }, [chooseDirectory, settingsForm.defaultDownloadDir]);

  const startDownload = useCallback(async () => {
    const trimmedShareUrl = shareUrl.trim();
    if (!trimmedShareUrl) {
      addLog("请先输入蓝奏云分享链接。");
      shareUrlRef.current?.focus();
      return;
    }

    const downloadDir = targetDir.trim() || settings.defaultDownloadDir;
    if (!downloadDir) {
      addLog("请先选择下载保存目录。");
      return;
    }

    setTargetDir(downloadDir);
    clearLog();
    setTotalProgress(0);
    setProcessRows(createProcessRows(settings.processCount));
    setDownloading(true);
    setCanceling(false);
    setStatusText("任务运行中");
    addLog("Getting file list...");

    try {
      const files = await invoke("start_download", {
        task: {
          shareUrl: trimmedShareUrl,
          password,
          targetDir: downloadDir,
          processCount: settings.processCount,
        },
      });
      setTotalProgress(100);
      setStatusText("下载完成");
      setCompleteText(`任务已完成，成功处理 ${files.length} 个文件。`);
      setCompleteOpen(true);
      setHistory(await invoke("load_history"));
    } catch (error) {
      if (String(error).toLowerCase().includes("cancel")) {
        addLog("下载已取消。");
        setStatusText("已取消");
      } else {
        addLog(`Error: ${error}`);
        setStatusText("任务失败");
      }
    } finally {
      setDownloading(false);
      setCanceling(false);
    }
  }, [addLog, clearLog, password, settings, shareUrl, targetDir]);

  const cancelDownload = useCallback(async () => {
    if (!downloading || canceling) return;

    setCanceling(true);
    setStatusText("正在取消");
    addLog("正在请求取消下载...");

    try {
      const cancelled = await invoke("cancel_download");
      if (!cancelled) {
        addLog("当前没有正在运行的下载任务。");
        setDownloading(false);
        setCanceling(false);
        setStatusText("等待任务");
      }
    } catch (error) {
      addLog(`Error: ${error}`);
      setCanceling(false);
    }
  }, [addLog, canceling, downloading]);

  const openSettings = useCallback(() => {
    setSettingsForm(settings);
    setSettingsOpen(true);
  }, [settings]);

  const saveSettings = useCallback(async () => {
    const previousDefaultDir = settings.defaultDownloadDir;
    const currentTargetDir = targetDir.trim();
    const shouldUpdateTargetDir = !currentTargetDir || currentTargetDir === previousDefaultDir;
    const savedSettings = await invoke("save_settings", {
      settings: {
        defaultDownloadDir: settingsForm.defaultDownloadDir.trim(),
        processCount: Number(settingsForm.processCount) || 1,
      },
    });

    applySettings(savedSettings);
    if (shouldUpdateTargetDir) {
      setTargetDir(savedSettings.defaultDownloadDir || "");
    }
    setSettingsOpen(false);
    addLog("设置已保存。");
  }, [addLog, applySettings, settings.defaultDownloadDir, settingsForm, targetDir]);

  const openHistory = useCallback(async () => {
    setHistory(await invoke("load_history"));
    setSelectedHistoryIndex(0);
    setHistoryOpen(true);
  }, []);

  const deleteHistory = useCallback(async () => {
    const nextHistory = await invoke("delete_history", { index: selectedHistoryIndex });
    setHistory(nextHistory);
    setSelectedHistoryIndex(Math.min(selectedHistoryIndex, Math.max(0, nextHistory.length - 1)));
  }, [selectedHistoryIndex]);

  const clearHistory = useCallback(async () => {
    setHistory(await invoke("clear_history"));
    setSelectedHistoryIndex(0);
  }, []);

  const openFolder = useCallback(async () => {
    const folder = targetDir.trim() || settings.defaultDownloadDir;
    if (folder) await invoke("open_folder", { path: folder });
    setCompleteOpen(false);
  }, [settings.defaultDownloadDir, targetDir]);

  useEffect(() => {
    let disposed = false;
    let unlisten = null;

    async function loadInitialState() {
      try {
        const initial = await invoke("initial_state");
        if (disposed) return;

        setHistory(initial.history || []);
        applySettings(initial, initial.maxProcesses);

        const stopListening = await listen("download-event", (event) => {
          const payload = event.payload;
          if (!payload) return;

          if (payload.type === "message") addLog(payload.message);
          if (payload.type === "totalProgress") setTotalProgress(clampProgress(payload.progress));
          if (payload.type === "processProgress") {
            updateProcessProgress(payload.slot, payload.fileName, payload.progress, payload.status);
          }
        });

        if (disposed) {
          stopListening();
          return;
        }
        unlisten = stopListening;
      } catch (error) {
        addLog(`Error: ${error}`);
      }
    }

    loadInitialState();

    return () => {
      disposed = true;
      if (unlisten) unlisten();
    };
  }, [addLog, applySettings, updateProcessProgress]);

  const selectedHistory = history[selectedHistoryIndex];
  const selectedHistoryDetails = useMemo(() => formatHistoryDetails(selectedHistory), [selectedHistory]);

  return (
    <Shell>
      <AppHeader downloading={downloading} onOpenHistory={openHistory} onOpenSettings={openSettings} />

      <Workspace>
        <DownloadForm
          canceling={canceling}
          downloading={downloading}
          password={password}
          processCount={settings.processCount}
          shareUrl={shareUrl}
          shareUrlRef={shareUrlRef}
          targetDir={targetDir}
          onCancel={cancelDownload}
          onChooseDirectory={chooseTargetDirectory}
          onPasswordChange={setPassword}
          onShareUrlChange={setShareUrl}
          onStart={startDownload}
          onTargetDirChange={setTargetDir}
        />

        <ProgressPanel processRows={processRows} statusText={statusText} totalProgress={totalProgress} />
        <LogPanel logs={logs} onClear={clearLog} />
      </Workspace>

      <SettingsDialog
        form={settingsForm}
        maxProcesses={maxProcesses}
        open={settingsOpen}
        onChange={setSettingsForm}
        onChooseDirectory={chooseDefaultDirectory}
        onClose={() => setSettingsOpen(false)}
        onSave={saveSettings}
      />

      <HistoryDialog
        details={selectedHistoryDetails}
        history={history}
        open={historyOpen}
        selectedIndex={selectedHistoryIndex}
        onClear={clearHistory}
        onClose={() => setHistoryOpen(false)}
        onDelete={deleteHistory}
        onSelect={setSelectedHistoryIndex}
      />

      <CompleteDialog
        open={completeOpen}
        text={completeText}
        onClose={() => setCompleteOpen(false)}
        onOpenFolder={openFolder}
      />
    </Shell>
  );
}
