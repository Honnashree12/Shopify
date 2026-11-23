import type { ReactNode } from "react";
import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth, getDisplayRole } from "./AuthContext";
import {
  Sparkles,
  Sun,
  Moon,
  LayoutDashboard,
  Package,
  Rocket,
  Bot,
  CheckCircle2,
  ShieldCheck,
  Search,
  Wrench,
  PlusCircle,
  FileText,
  Activity,
  LogOut,
  Bell,
  ChevronDown
} from "lucide-react";

interface NavItemDef {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: string[];
}

interface NavSectionDef {
  title: string;
  items: NavItemDef[];
}

const NAV_SECTIONS: NavSectionDef[] = [
  {
    title: "WORK",
    items: [
      {
        to: "/",
        label: "Overview",
        icon: LayoutDashboard,
        roles: ["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]
      },
      {
        to: "/launches",
        label: "Product Catalogue",
        icon: Package,
        roles: ["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]
      },
      {
        to: "/?view=my-work",
        label: "Launches",
        icon: Rocket,
        roles: ["CATALOGUE_ADMIN", "APPROVER"]
      },
    ]
  },
  {
    title: "OPERATIONS",
    items: [
      {
        to: "/agents",
        label: "Agents",
        icon: Bot,
        roles: ["PLATFORM_ADMIN", "APPROVER", "CATALOGUE_ADMIN"]
      },
      {
        to: "/?view=approvals",
        label: "Approvals",
        icon: CheckCircle2,
        roles: ["CATALOGUE_ADMIN", "APPROVER"]
      },
      {
        to: "/validation",
        label: "Product Validation",
        icon: ShieldCheck,
        roles: ["PLATFORM_ADMIN", "APPROVER", "CATALOGUE_ADMIN"]
      },
      {
        to: "/seo",
        label: "SEO Dashboard",
        icon: Search,
        roles: ["PLATFORM_ADMIN", "APPROVER", "CATALOGUE_ADMIN"]
      },
      {
        to: "/workshops",
        label: "Workshop Agent",
        icon: Wrench,
        roles: ["PLATFORM_ADMIN", "APPROVER", "CATALOGUE_ADMIN"]
      },
      {
        to: "/launches/new",
        label: "Add Product",
        icon: PlusCircle,
        roles: ["CATALOGUE_ADMIN"]
      },
    ]
  },
  {
    title: "SYSTEM",
    items: [
      {
        to: "/activity",
        label: "Audit Logs",
        icon: FileText,
        roles: ["PLATFORM_ADMIN"]
      },
      {
        to: "/?view=health",
        label: "Health Checks",
        icon: Activity,
        roles: ["PLATFORM_ADMIN"]
      },
    ]
  }
];

export function AppShell({ title, crumbs, children }: { title: string; crumbs?: string; children: ReactNode }) {
  const { currentUser, loginAs, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Dark/Light theme state initialized from localStorage
  const [isDark, setIsDark] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem("agentic_boss_pod_theme");
      if (saved) return saved === "dark";
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    } catch {
      return false;
    }
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    try {
      localStorage.setItem("agentic_boss_pod_theme", isDark ? "dark" : "light");
    } catch {}
  }, [isDark]);

  const toggleTheme = () => setIsDark(prev => !prev);

  const currentPath = location.pathname + location.search;

  const isLinkActive = (to: string) => {
    if (to === "/") {
      return currentPath === "/" || currentPath === "/?view=overview" || currentPath === "";
    }
    return currentPath === to;
  };

  const handleRoleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value as "catalogue" | "approver" | "admin";
    loginAs(val);
    navigate("/");
  };

  const handleSignOut = () => {
    logout();
    navigate("/login");
  };

  const matchesSearch = (label: string) => {
    if (!searchQuery.trim()) return true;
    return label.toLowerCase().includes(searchQuery.toLowerCase());
  };

  return (
    <div
      className={`shell ${isDark ? "dark" : ""}`}
      style={{
        display: "grid",
        gridTemplateColumns: collapsed ? "70px 1fr" : "var(--nav-width) 1fr",
        minHeight: "100vh",
        transition: "grid-template-columns 0.2s cubic-bezier(0.16, 1, 0.3, 1)"
      }}
    >
      {/* Sidebar Navigation */}
      <nav
        className="shell__nav"
        aria-label="Primary Navigation"
        style={{
          width: collapsed ? "70px" : "var(--nav-width)",
          padding: collapsed ? "16px 8px" : "16px 12px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          position: "sticky",
          top: 0,
          height: "100vh",
          overflowY: "auto",
          borderRight: "1px solid var(--border-color)",
          backgroundColor: "var(--bg-surface)",
          backdropFilter: "var(--glass-blur)",
          zIndex: 40
        }}
      >
        {/* Brand Banner */}
        <div className="brand" style={{ padding: "0 4px 6px" }}>
          <button
            type="button"
            className="workspace-switcher"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "KiddyPi Store · Subhanu Cockpit"}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              width: "100%",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              background: "transparent",
              color: "var(--text-primary)",
              textAlign: "left",
              border: "1px solid transparent",
              cursor: "pointer"
            }}
          >
            <div
              className="workspace-switcher__mark"
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "var(--radius-sm)",
                background: "linear-gradient(135deg, var(--color-deep-indigo), var(--color-primary-cyan))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                boxShadow: "0 2px 8px color-mix(in srgb, var(--color-deep-indigo) 40%, transparent)",
                flexShrink: 0
              }}
            >
              <Sparkles size={18} />
            </div>
            {!collapsed && (
              <>
                <div className="workspace-switcher__text" style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
                  <span style={{ fontSize: "13px", fontWeight: 800, fontFamily: "var(--font-display)", color: "var(--text-primary)", lineHeight: 1.2 }}>
                    KiddyPi Store
                  </span>
                  <span style={{ fontSize: "10.5px", fontWeight: 600, color: "var(--text-muted)" }}>
                    Subhanu Cockpit
                  </span>
                </div>
                <ChevronDown size={14} style={{ color: "var(--text-muted)" }} />
              </>
            )}
          </button>
        </div>

        {/* Jump-To Filter Input */}
        {!collapsed && (
          <div className="nav-search-box" style={{ padding: "0 4px" }}>
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <Search size={13} style={{ position: "absolute", left: "10px", color: "var(--text-muted)" }} />
              <input
                id="nav-jump-input"
                type="text"
                placeholder="Jump to…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  height: "32px",
                  padding: "0 10px 0 28px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-subtle)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                  fontSize: "12px",
                  fontWeight: 500,
                  outline: "none"
                }}
              />
            </div>
          </div>
        )}

        {/* Navigation Sections */}
        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "14px" }}>
          {NAV_SECTIONS.map((section) => {
            const visibleItems = section.items
              .filter((item) => currentUser && item.roles.includes(currentUser.role))
              .filter((item) => matchesSearch(item.label));

            if (visibleItems.length === 0) return null;

            return (
              <div key={section.title} style={{ display: "flex", flexDirection: "column" }}>
                {!collapsed && (
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      color: "var(--text-muted)",
                      padding: "4px 8px 6px"
                    }}
                  >
                    {section.title}
                  </span>
                )}
                <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                  {visibleItems.map((item) => {
                    const active = isLinkActive(item.to);
                    const IconComponent = item.icon;
                    return (
                      <Link
                        key={item.to}
                        to={item.to}
                        title={collapsed ? item.label : undefined}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          height: "36px",
                          padding: collapsed ? "0" : "0 10px",
                          justifyContent: collapsed ? "center" : "flex-start",
                          borderRadius: "var(--radius-sm)",
                          fontSize: "13px",
                          fontWeight: active ? 700 : 600,
                          color: active ? "#ffffff" : "var(--text-secondary)",
                          background: active
                            ? "linear-gradient(135deg, var(--accent-primary), var(--accent-primary-hover))"
                            : "transparent",
                          boxShadow: active
                            ? "0 4px 12px color-mix(in srgb, var(--accent-primary) 35%, transparent)"
                            : "none",
                          textDecoration: "none",
                          transition: "all 0.15s ease"
                        }}
                      >
                        <IconComponent size={16} style={{ color: active ? "#ffffff" : "inherit", flexShrink: 0 }} />
                        {!collapsed && <span>{item.label}</span>}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Sidebar Footer: Agent Health, Port Info, Theme Toggle, User Profile */}
        <div
          className="nav-footer"
          style={{
            marginTop: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            borderTop: "1px solid var(--border-color)",
            paddingTop: "12px"
          }}
        >
          {/* Health Strip */}
          {!collapsed ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "6px 10px",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-subtle)",
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--text-secondary)"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span
                  style={{
                    width: "7px",
                    height: "7px",
                    borderRadius: "50%",
                    background: "var(--status-live)",
                    boxShadow: "0 0 6px var(--status-live)",
                    display: "inline-block"
                  }}
                />
                <span>All agents healthy</span>
              </div>
              <span style={{ fontSize: "10.5px", color: "var(--text-muted)" }}>18ms</span>
            </div>
          ) : (
            <div style={{ display: "flex", justifyContent: "center" }} title="All agents healthy · 18ms">
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: "var(--status-live)",
                  boxShadow: "0 0 6px var(--status-live)",
                  display: "inline-block"
                }}
              />
            </div>
          )}

          {/* Theme Toggle Pill Button */}
          <button
            type="button"
            onClick={toggleTheme}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: collapsed ? "center" : "space-between",
              width: "100%",
              padding: "7px 10px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-color)",
              backgroundColor: "var(--bg-subtle)",
              color: "var(--text-primary)",
              cursor: "pointer",
              fontSize: "11.5px",
              fontWeight: 600,
              transition: "all 0.15s ease"
            }}
            title={`Switch to ${isDark ? "Light" : "Dark"} Theme`}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {isDark ? <Moon size={14} color="#38bdf8" /> : <Sun size={14} color="#f59e0b" />}
              {!collapsed && <span>{isDark ? "Dark Theme" : "Light Theme"}</span>}
            </div>
            {!collapsed && <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>Toggle</span>}
          </button>

          {/* Port and Status Details */}
          {!collapsed && (
            <div style={{ fontSize: "10.5px", color: "var(--text-muted)", padding: "0 4px", lineHeight: 1.3 }}>
              <div>Local Port: <strong style={{ color: "var(--text-secondary)" }}>8000</strong></div>
              <div style={{ marginTop: "2px", fontSize: "10px" }}>Connected to Shopify Live</div>
            </div>
          )}

          {/* User Profile Strip */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "8px",
              padding: collapsed ? "6px 0" : "8px 6px 4px",
              borderTop: "1px solid var(--border-color)"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
              <span
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, var(--accent-primary), var(--accent-primary-hover))",
                  color: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "11px",
                  fontWeight: 800,
                  flexShrink: 0
                }}
                title={`${currentUser?.name} (${getDisplayRole(currentUser?.role)})`}
              >
                {currentUser?.avatar || "?"}
              </span>
              {!collapsed && (
                <div style={{ display: "flex", flexDirection: "column", minWidth: 0, lineHeight: 1.2 }}>
                  <span style={{ fontSize: "12.5px", fontWeight: 700, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {currentUser?.name}
                  </span>
                  <span style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                    {getDisplayRole(currentUser?.role)}
                  </span>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={handleSignOut}
              style={{
                color: "var(--text-muted)",
                padding: "6px",
                borderRadius: "var(--radius-sm)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer"
              }}
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </nav>

      {/* Main Layout Area */}
      <div className="shell__main" style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Sticky Glass Topbar */}
        <header
          className="topbar"
          style={{
            height: "var(--topbar-height)",
            position: "sticky",
            top: 0,
            zIndex: 30,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
            backgroundColor: "var(--bg-surface)",
            backdropFilter: "var(--glass-blur)",
            borderBottom: "1px solid var(--border-color)",
            boxShadow: "var(--shadow-1)"
          }}
        >
          {/* Breadcrumbs & Title */}
          <div className="topbar__left" style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
            {crumbs && (
              <div className="topbar__crumbs" style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px" }}>
                <span>{crumbs}</span>
                <span style={{ opacity: 0.5 }}>/</span>
              </div>
            )}
            <h2 className="topbar__title" style={{ fontSize: "16px", fontWeight: 800, fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>
              {title}
            </h2>
          </div>

          {/* Quick Command Search Pill */}
          <div className="topbar__center" style={{ flex: 1, maxWidth: "400px", margin: "0 20px" }}>
            <button
              type="button"
              className="topbar-command-pill"
              aria-label="Quick command search"
              style={{
                width: "100%",
                height: "34px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0 12px",
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--bg-subtle)",
                border: "1px solid var(--border-color)",
                color: "var(--text-muted)",
                fontSize: "12px",
                cursor: "pointer"
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Search size={14} />
                <span>Quick command...</span>
              </span>
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  backgroundColor: "var(--bg-surface)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "4px",
                  padding: "1px 5px"
                }}
              >
                ⌘K
              </span>
            </button>
          </div>

          {/* Right Header Actions */}
          <div className="topbar__right" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {/* Shopify Live Status Chip */}
            <div
              className="env-chip"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "4px 10px",
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--status-live-bg)",
                border: "1px solid color-mix(in srgb, var(--status-live) 35%, transparent)",
                color: "var(--status-live)",
                fontSize: "11px",
                fontWeight: 700
              }}
              title="Connected to Shopify Production Store"
            >
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "var(--status-live)", boxShadow: "0 0 6px var(--status-live)" }} />
              <span>Production</span>
            </div>

            {/* Header Theme Toggle */}
            <button
              type="button"
              onClick={toggleTheme}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "34px",
                height: "34px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-color)",
                backgroundColor: "var(--bg-surface)",
                color: "var(--text-secondary)",
                cursor: "pointer"
              }}
              title={`Switch to ${isDark ? "Light" : "Dark"} Mode`}
            >
              {isDark ? <Sun size={15} color="#f59e0b" /> : <Moon size={15} color="#6366f1" />}
            </button>

            {/* Notification Icon */}
            <button
              type="button"
              style={{
                position: "relative",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "34px",
                height: "34px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-color)",
                backgroundColor: "var(--bg-surface)",
                color: "var(--text-secondary)",
                cursor: "pointer"
              }}
              title="Notifications"
            >
              <Bell size={16} />
              <span
                style={{
                  position: "absolute",
                  top: "6px",
                  right: "6px",
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: "var(--accent-primary)"
                }}
              />
            </button>

            {/* Identity Role Switcher */}
            {currentUser?.isMock ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "3px 8px 3px 6px",
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--bg-subtle)",
                  border: "1px solid var(--border-color)",
                  boxShadow: "var(--shadow-sm)"
                }}
                title="Development identity switcher"
              >
                <span
                  style={{
                    width: "22px",
                    height: "22px",
                    borderRadius: "50%",
                    background: "var(--accent-primary)",
                    color: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "10px",
                    fontWeight: 700
                  }}
                >
                  {currentUser?.avatar || "?"}
                </span>
                <span style={{ fontSize: "9.5px", fontWeight: 800, color: "var(--text-muted)" }}>DEV</span>
                <select
                  id="role-select"
                  value={
                    currentUser
                      ? currentUser.role === "CATALOGUE_ADMIN"
                        ? "catalogue"
                        : currentUser.role === "APPROVER"
                        ? "approver"
                        : "admin"
                      : "catalogue"
                  }
                  onChange={handleRoleChange}
                  style={{
                    background: "transparent",
                    border: "none",
                    fontSize: "12px",
                    fontWeight: 700,
                    cursor: "pointer",
                    color: "var(--text-primary)",
                    outline: "none"
                  }}
                >
                  <option value="catalogue">Catalogue Manager (Lakshmi)</option>
                  <option value="approver">Product Launch Manager (Sandeep)</option>
                  <option value="admin">Platform Administrator</option>
                </select>
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "4px 10px",
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--bg-subtle)",
                  border: "1px solid var(--border-color)"
                }}
              >
                <span
                  style={{
                    width: "24px",
                    height: "24px",
                    borderRadius: "50%",
                    background: "var(--accent-primary)",
                    color: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "10.5px",
                    fontWeight: 800
                  }}
                >
                  {currentUser?.avatar || "?"}
                </span>
                <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
                  <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)" }}>
                    {currentUser?.name}
                  </span>
                  <span style={{ fontSize: "9.5px", color: "var(--text-muted)" }}>
                    {getDisplayRole(currentUser?.role)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </header>

        {/* Main View Area */}
        <main
          className="boss-pod-main"
          style={{
            flex: 1,
            padding: "24px",
            maxWidth: "1400px",
            width: "100%",
            margin: "0 auto",
            boxSizing: "border-box"
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppShell;
