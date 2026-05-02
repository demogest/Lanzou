import { Button, ButtonGroup } from "./ui.jsx";

export default function AppHeader({ downloading, onOpenHistory, onOpenSettings }) {
  return (
    <header className="app-header">
      <div>
        <h1>蓝奏云下载器</h1>
        <p>粘贴分享链接，选择保存目录，批量下载同一分享页内的文件。</p>
      </div>
      <ButtonGroup className="header-actions">
        <Button id="settingsBtn" disabled={downloading} onClick={onOpenSettings}>
          下载设置
        </Button>
        <Button id="historyBtn" onClick={onOpenHistory}>
          下载历史
        </Button>
      </ButtonGroup>
    </header>
  );
}
