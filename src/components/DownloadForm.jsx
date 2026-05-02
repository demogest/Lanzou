import { Button, ButtonGroup, Field, InlineField, Panel, TextInput } from "./ui.jsx";

export default function DownloadForm({
  canceling,
  downloading,
  onCancel,
  onChooseDirectory,
  onPasswordChange,
  onShareUrlChange,
  onStart,
  onTargetDirChange,
  password,
  processCount,
  shareUrl,
  shareUrlRef,
  targetDir,
}) {
  return (
    <Panel className="input-panel">
      <Field id="shareUrl" label="分享链接">
        <TextInput
          id="shareUrl"
          placeholder="粘贴蓝奏云分享链接"
          ref={shareUrlRef}
          value={shareUrl}
          onChange={(event) => onShareUrlChange(event.target.value)}
        />
      </Field>

      <Field id="password" label="提取码">
        <TextInput
          id="password"
          placeholder="没有提取码可留空"
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
        />
      </Field>

      <Field id="targetDir" label="保存位置">
        <InlineField>
          <TextInput
            id="targetDir"
            placeholder="选择下载保存目录"
            value={targetDir}
            onChange={(event) => onTargetDirChange(event.target.value)}
          />
          <Button id="chooseDirBtn" disabled={downloading} onClick={onChooseDirectory}>
            选择目录
          </Button>
        </InlineField>
      </Field>

      <div className="form-footer">
        <span id="processHint">并发进程：{processCount}</span>
        <ButtonGroup className="download-actions">
          <Button id="cancelBtn" disabled={!downloading || canceling} onClick={onCancel}>
            {canceling ? "取消中..." : "取消下载"}
          </Button>
          <Button id="startBtn" disabled={downloading} variant="primary" onClick={onStart}>
            {downloading ? "下载中..." : "开始下载"}
          </Button>
        </ButtonGroup>
      </div>
    </Panel>
  );
}
