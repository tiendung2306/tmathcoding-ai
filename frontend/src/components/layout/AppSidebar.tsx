import React from "react";
import {
  Cpu,
  Layers,
  Activity,
  Tags,
  Users,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  X
} from "lucide-react";
import { cn } from "../../lib/utils";
import { TooltipProvider } from "../ui/tooltip";

interface AppSidebarProps {
  activeTab: "student" | "teacher";
  setActiveTab: (tab: "student" | "teacher") => void;
  activeSubSection?: string;
  onSectionClick?: (section: string) => void;
  isCollapsed: boolean;
  setIsCollapsed: (collapsed: boolean) => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const AppSidebar: React.FC<AppSidebarProps> = ({
  activeTab,
  setActiveTab,
  onSectionClick,
  isCollapsed,
  setIsCollapsed,
  isMobileOpen = false,
  onCloseMobile,
}) => {
  const studentNavItems = [
    {
      id: "overview",
      label: "Tổng quan học lực",
      icon: Activity,
    },
    {
      id: "skill-tree",
      label: "Cây kỹ năng",
      icon: Layers,
    },
    {
      id: "tag-analytics",
      label: "Thống kê chuyên đề",
      icon: Tags,
    },
  ];

  const teacherNavItems = [
    {
      id: "heatmap",
      label: "Bản đồ năng lực lớp",
      icon: BookOpen,
    },
    {
      id: "students",
      label: "Tra cứu học sinh",
      icon: Users,
    },
  ];

  return (
    <TooltipProvider delayDuration={150}>
      {/* Mobile Overlay Backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-slate-950/50 z-40 md:hidden transition-opacity"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "h-screen flex flex-col border-r border-border bg-sidebar transition-all duration-200 z-50 select-none",
          "fixed top-0 bottom-0 left-0 md:sticky md:top-0",
          isMobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          isCollapsed ? "w-16" : "w-64"
        )}
      >
        {/* Brand Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-border">
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-8 w-8 rounded-md bg-brand-primary/15 border border-brand-primary/30 flex items-center justify-center text-brand-primary flex-shrink-0">
              <Cpu className="w-4 h-4" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col min-w-0">
                <span className="font-bold text-sm text-text-primary tracking-tight truncate">
                  tmath OJ
                </span>
                <span className="text-[11px] text-text-tertiary truncate">
                  Hệ thống đánh giá
                </span>
              </div>
            )}
          </div>

          {/* Close button on mobile */}
          {isMobileOpen && (
            <button
              type="button"
              onClick={onCloseMobile}
              className="md:hidden p-2 -mr-2 text-text-secondary hover:text-text-primary rounded-md hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              aria-label="Đóng thanh điều hướng"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation Content */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
          {/* Student Mode Switcher */}
          <div>
            {!isCollapsed && (
              <div className="px-2 pb-1.5 text-xs font-medium text-text-tertiary">
                Học sinh
              </div>
            )}
            <div className="space-y-0.5">
              <button
                type="button"
                onClick={() => {
                  setActiveTab("student");
                  onCloseMobile?.();
                }}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs font-medium transition-colors text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary",
                  activeTab === "student"
                    ? "bg-slate-900 text-white shadow-xs"
                    : "text-text-secondary hover:text-text-primary hover:bg-card-hover"
                )}
              >
                <Activity className="w-4 h-4 flex-shrink-0" />
                {!isCollapsed && <span className="truncate">Học sinh</span>}
              </button>

              {!isCollapsed && activeTab === "student" && (
                <div className="pl-4 pt-1 space-y-0.5 border-l border-border/60 ml-4 my-1">
                  {studentNavItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        onSectionClick?.(item.id);
                        onCloseMobile?.();
                      }}
                      className="w-full text-left text-xs py-1.5 px-2 text-text-secondary hover:text-text-primary hover:bg-card-hover rounded-sm flex items-center justify-between transition-colors"
                    >
                      <span className="truncate">{item.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Teacher Mode Switcher */}
          <div>
            {!isCollapsed && (
              <div className="px-2 pb-1.5 text-xs font-medium text-text-tertiary">
                Giáo viên
              </div>
            )}
            <div className="space-y-0.5">
              <button
                type="button"
                onClick={() => {
                  setActiveTab("teacher");
                  onCloseMobile?.();
                }}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs font-medium transition-colors text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary",
                  activeTab === "teacher"
                    ? "bg-slate-900 text-white shadow-xs"
                    : "text-text-secondary hover:text-text-primary hover:bg-card-hover"
                )}
              >
                <Users className="w-4 h-4 flex-shrink-0" />
                {!isCollapsed && <span className="truncate">Giáo viên</span>}
              </button>

              {!isCollapsed && activeTab === "teacher" && (
                <div className="pl-4 pt-1 space-y-0.5 border-l border-border/60 ml-4 my-1">
                  {teacherNavItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        onSectionClick?.(item.id);
                        onCloseMobile?.();
                      }}
                      className="w-full text-left text-xs py-1.5 px-2 text-text-secondary hover:text-text-primary hover:bg-card-hover rounded-sm flex items-center justify-between transition-colors"
                    >
                      <span className="truncate">{item.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer Status & Collapse Toggle */}
        <div className="p-2 border-t border-border space-y-2">
          {!isCollapsed && (
            <div className="p-2 rounded-md bg-card-subtle border border-border text-xs flex items-center justify-between text-text-secondary">
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-600 shrink-0" />
                <span>Trạng thái hệ thống</span>
              </span>
              <span className="font-medium text-emerald-700 text-[11px]">Sẵn sàng</span>
            </div>
          )}

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="w-full flex items-center justify-center p-1.5 rounded-md hover:bg-card-hover text-text-secondary hover:text-text-primary transition-colors text-xs gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              aria-expanded={!isCollapsed}
              aria-label={isCollapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
            >
              {isCollapsed ? (
                <ChevronRight className="w-4 h-4" />
              ) : (
                <>
                  <ChevronLeft className="w-4 h-4" />
                  <span className="text-xs">Thu gọn</span>
                </>
              )}
            </button>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
};
