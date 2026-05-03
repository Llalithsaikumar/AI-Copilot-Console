import { UserButton } from "@clerk/react";

export default function AppHeader({ title = "AI Copilot Console", subtitle, accountName, role }) {
  return (
    <header className="app-header glass-panel">
      <div className="header-left">
        <h1 className="header-title">{title}</h1>
        {subtitle && <p className="header-sub">{subtitle}</p>}
      </div>
      <div className="header-right">
        <div className="header-profile">
          <div className="header-profile-text">
            <span className="header-name">{accountName || "Account"}</span>
            {role && <span className="header-role">{role}</span>}
          </div>
          <UserButton afterSignOutUrl="/" />
        </div>
      </div>
    </header>
  );
}
