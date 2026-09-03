import React, { useState, useEffect } from 'react';
import { AppSidebar } from './components/layout/AppSidebar';
import { Header } from './components/layout/Header';
import { StudentDashboard } from './pages/StudentDashboard';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { searchStudents } from './services/api';
import { Badge } from './components/ui/badge';
import { Card } from './components/ui/card';
import { X, Search } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'student' | 'teacher'>('student');
  const [selectedStudentId, setSelectedStudentId] = useState<number>(1024);
  const [selectedStudentName, setSelectedStudentName] = useState<string>('User 1024');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [, setIsSearching] = useState<boolean>(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);
  const [pendingSection, setPendingSection] = useState<string | null>(null);

  // Close search on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSearchResults([]);
        setIsMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Sub-nav: đợi section render xong (dữ liệu load async) rồi cuộn tới
  useEffect(() => {
    if (!pendingSection) return;
    let attempts = 0;
    const timer = setInterval(() => {
      const el = document.getElementById(`section-${pendingSection}`);
      attempts++;
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        clearInterval(timer);
        setPendingSection(null);
      } else if (attempts > 20) {
        clearInterval(timer);
        setPendingSection(null);
      }
    }, 150);
    return () => clearInterval(timer);
  }, [pendingSection]);

  const onCloseMobileRef = () => setIsMobileMenuOpen(false);

  const handleSectionClick = (section: string) => {
    const target = section === 'students' ? 'heatmap' : section;
    const tab = ['overview', 'skill-tree', 'tag-analytics'].includes(section)
      ? 'student'
      : 'teacher';
    setActiveTab(tab);
    setPendingSection(target);
    onCloseMobileRef();
  };

  const handleSearchSubmit = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const results = await searchStudents(searchQuery);
      setSearchResults(results);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectStudentFromSearch = (userId: number, name?: string) => {
    setSelectedStudentId(userId);
    if (name) setSelectedStudentName(name);
    setActiveTab('student');
    setSearchResults([]);
    setSearchQuery('');
  };

  return (
    <div className="min-h-screen bg-app text-text-primary flex">
      {/* App Sidebar with Mobile Support */}
      <AppSidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onSectionClick={handleSectionClick}
        isCollapsed={isSidebarCollapsed}
        setIsCollapsed={setIsSidebarCollapsed}
        isMobileOpen={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <Header
          activeTab={activeTab}
          studentId={selectedStudentId}
          studentName={selectedStudentName}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onSearchSubmit={handleSearchSubmit}
          onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        />

        {/* Global Search Results Floating Dialog Overlay */}
        {searchResults.length > 0 && (
          <div
            className="fixed inset-0 z-40 bg-slate-950/50 flex items-start justify-center pt-16 px-4"
            onClick={() => setSearchResults([])}
          >
            <Card
              className="p-4 w-full max-w-lg shadow-xl z-50 bg-card border-border"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between pb-2 border-b border-border mb-2">
                <div className="flex items-center gap-2">
                  <Search className="w-3.5 h-3.5 text-text-secondary" />
                  <h3 className="text-xs font-semibold text-text-primary">
                    Kết quả tìm kiếm ({searchResults.length})
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setSearchResults([])}
                  className="p-1.5 text-text-secondary hover:text-text-primary rounded-md hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
                  aria-label="Đóng kết quả"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                {searchResults.map((st) => (
                  <div
                    key={st.user_id}
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSelectStudentFromSearch(st.user_id, st.name)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleSelectStudentFromSearch(st.user_id, st.name);
                      }
                    }}
                    className="p-2.5 bg-card-subtle/50 hover:bg-card-subtle border border-border hover:border-border-strong rounded-md cursor-pointer transition-colors flex items-center justify-between focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-medium text-text-primary">{st.name}</span>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          #{st.user_id}
                        </Badge>
                      </div>
                      <span className="text-[11px] text-text-secondary">
                        @{st.username} • {st.problem_count} bài nộp
                      </span>
                    </div>
                    <Badge variant="ac" className="text-xs font-mono">
                      {st.points} pts
                    </Badge>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* Page Views */}
        <main className="flex-1 overflow-y-auto">
          {activeTab === 'student' ? (
            <StudentDashboard studentId={selectedStudentId} />
          ) : (
            <TeacherDashboard
              onSelectStudent={(id, name) => handleSelectStudentFromSearch(id, name)}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
