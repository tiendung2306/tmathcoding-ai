import React, { useState, useEffect } from 'react';
import { RoleSelect, Role } from './components/RoleSelect';
import { Header } from './components/layout/Header';
import { StudentDashboard } from './pages/StudentDashboard';
import { AdminDashboard } from './pages/AdminDashboard';
import { ClassTable } from './components/ClassTable';
import { ClassStudentsGrid } from './components/ClassStudentsGrid';
import { VirtualClassSessions } from './components/VirtualClassSessions';
import { VirtualClassLiveRoom } from './pages/VirtualClassLiveRoom';
import { searchStudents, fetchClassStudents } from './services/api';
import { ClassListQuery, ClassStudentItemData } from './types';
import { Badge } from './components/ui/badge';
import { Card } from './components/ui/card';
import { X, Search } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<Role | null>(null);
  const [studentStep, setStudentStep] = useState<'classes' | 'students' | 'detail'>('classes');
  const [virtualClassStep, setVirtualClassStep] = useState<'classes' | 'sessions' | 'live'>('classes');
  
  const [classListQuery, setClassListQuery] = useState<ClassListQuery>({
    page: 1, page_size: 24, q: '', sort_by: 'creation_date', sort_order: 'desc', starred_only: false,
  });
  const [selectedClass, setSelectedClass] = useState<{ id: number; name: string } | null>(null);
  const selectedOrgId = selectedClass?.id;
  const currentClassName = selectedClass?.name;
  const [classStudents, setClassStudents] = useState<ClassStudentItemData[]>([]);
  const [studentsLoading, setStudentsLoading] = useState<boolean>(false);

  const [selectedStudentId, setSelectedStudentId] = useState<number>(7);
  const [selectedStudentName, setSelectedStudentName] = useState<string>('Nguyễn Khắc Tùng Lâm');
  
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [selectedSessionName, setSelectedSessionName] = useState<string>('');
  const [selectedSessionIsActive, setSelectedSessionIsActive] = useState<boolean>(true);

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);

  // Load class students whenever selectedOrgId changes
  useEffect(() => {
    if (selectedOrgId) {
      loadStudentsOfClass(selectedOrgId);
    }
  }, [selectedOrgId]);

  const loadStudentsOfClass = async (orgId: number) => {
    setStudentsLoading(true);
    try {
      const students = await fetchClassStudents(orgId);
      setClassStudents(students);

      // If current student is not in this new class, select the first student of the class
      if (students.length > 0) {
        const studentExists = students.some((s) => s.user_id === selectedStudentId);
        if (!studentExists) {
          setSelectedStudentId(students[0].user_id);
          setSelectedStudentName(students[0].name);
        }
      }
    } catch (err) {
      console.error('Không tải được danh sách học sinh theo lớp:', err);
    } finally {
      setStudentsLoading(false);
    }
  };

  // Close search on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSearchResults([]);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

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

  const handleSelectClass = (orgId: number, className?: string) => {
    setSelectedClass({ id: orgId, name: className || `Lớp #${orgId}` });
    if (activeTab === 'student') {
      setStudentStep('students');
    } else if (activeTab === 'teacher') {
      setVirtualClassStep('sessions');
    }
  };

  const handleSelectStudent = (userId: number, name?: string) => {
    setSelectedStudentId(userId);
    if (name) setSelectedStudentName(name);
    setStudentStep('detail');
    setActiveTab('student');
    setSearchResults([]);
    setSearchQuery('');
  };

  const handleRoleSelect = (role: Role) => {
    setActiveTab(role);
    if (role === 'student') setStudentStep('classes');
    if (role === 'teacher') setVirtualClassStep('classes');
  };

  const handleBackToClasses = () => {
    setStudentStep('classes');
  };

  const handleBackToStudents = () => {
    setStudentStep('students');
  };

  if (!activeTab) {
    return <RoleSelect onSelectRole={handleRoleSelect} />;
  }

  return (
    <div className="min-h-screen bg-app text-text-primary flex flex-col">
      {/* Top Header */}
      <Header
        activeTab={activeTab}
        onChangeRole={() => setActiveTab(null)}
        studentId={selectedStudentId}
        studentName={selectedStudentName}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
        studentStep={studentStep}
        onNavigateStudentStep={(step) => setStudentStep(step)}
        virtualClassStep={virtualClassStep}
        onNavigateVirtualClassStep={(step) => setVirtualClassStep(step)}
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
                    onClick={() => handleSelectStudent(st.user_id, st.name)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleSelectStudent(st.user_id, st.name);
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
                        {st.problem_count} bài nộp
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
            studentStep === 'classes' ? (
              <ClassTable
                query={classListQuery}
                onQueryChange={setClassListQuery}
                onSelectClass={handleSelectClass}
              />
            ) : studentStep === 'students' && selectedOrgId !== undefined ? (
              <ClassStudentsGrid
                classNameTitle={currentClassName || `Lớp #${selectedOrgId}`}
                classId={selectedOrgId}
                students={classStudents}
                loading={studentsLoading}
                onSelectStudent={handleSelectStudent}
                onBackToClasses={handleBackToClasses}
              />
            ) : (
              <StudentDashboard
                studentId={selectedStudentId}
                classStudents={classStudents}
                currentClassName={currentClassName}
                onSelectStudent={handleSelectStudent}
                onBackToStudents={handleBackToStudents}
                onBackToClasses={handleBackToClasses}
              />
            )
          ) : activeTab === 'teacher' ? (
            virtualClassStep === 'classes' ? (
              <ClassTable
                query={classListQuery}
                onQueryChange={setClassListQuery}
                onSelectClass={handleSelectClass}
              />
            ) : virtualClassStep === 'sessions' ? (
              <VirtualClassSessions
                selectedOrgId={selectedOrgId ?? undefined}
                className={currentClassName}
                onEnterSession={(sessionId, sessionName, isActive) => {
                  setSelectedSessionId(sessionId);
                  setSelectedSessionName(sessionName);
                  setSelectedSessionIsActive(isActive);
                  setVirtualClassStep('live');
                }}
              />
            ) : (
              selectedSessionId && (
                <VirtualClassLiveRoom
                  sessionId={selectedSessionId}
                  sessionName={selectedSessionName}
                  isActive={selectedSessionIsActive}
                  onSessionStopped={() => setVirtualClassStep('sessions')}
                />
              )
            )
          ) : (
            <AdminDashboard />
          )}
        </main>
    </div>
  );
};

export default App;
