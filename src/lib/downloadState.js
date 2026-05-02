export const defaultSettings = {
  defaultDownloadDir: "",
  processCount: 1,
};

export function clampProgress(progress) {
  return Math.max(0, Math.min(100, Number(progress) || 0));
}

export function createProcessRows(count) {
  return Array.from({ length: Math.max(1, Number(count) || 1) }, (_, index) => ({
    slot: index + 1,
    fileName: "",
    progress: 0,
    status: "等待",
  }));
}

export function classifyLog(message) {
  const text = String(message);
  const lower = text.toLowerCase();
  if (lower.includes("error") || text.includes("失败")) return "错误";
  if (text.includes("解析") || text.includes("提取") || lower.includes("resolving")) return "解析";
  if (text.includes("完成") || lower.includes("finished")) return "完成";
  return "下载";
}

function fileLine(file, index) {
  if (typeof file === "string") {
    return `${index + 1}. ${file}`;
  }

  return `${index + 1}. ${file?.name || ""} | ${file?.size || "未知"}\n   ${file?.path || ""}`;
}

export function formatHistoryDetails(record) {
  if (!record) return "暂无下载记录。";

  const files = (record.files || []).map(fileLine).join("\n");
  return (
    `时间：${record.time || "-"}\n` +
    `URL：${record.shareUrl || "-"}\n` +
    `密码：${record.password || "（无）"}\n` +
    `完成时间：${record.finishedTime || record.time || "-"}\n` +
    `保存目录：${record.targetDir || "-"}\n` +
    `并发进程：${record.processCount || 1}\n` +
    `下载文件数：${record.downloadedCount || 0}\n\n` +
    `下载文件信息：\n${files || "无"}`
  );
}
