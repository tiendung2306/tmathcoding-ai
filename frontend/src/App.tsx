import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { StudentDashboard } from './pages/StudentDashboard';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { searchStudents } from './services/api';

export function App() {
  const [activeTab, setActiveTab] = useState<'student' | 'teacher'>('student');
  const [selectedStudentId, setSelectedStudentId] = useState<number>(1024);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);

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

  const handleSelectStudentFromSearch = (userId: number) => {
    setSelectedStudentId(userId);
    setActiveTab('student');
    setSearchResults([]);
    setSearchQuery('');
  };

  return (
    <div className="min-h-screen bg-dark-bg text-slate-100 flex flex-col">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
      />

      {/* Global Search Results Dropdown Overlay */}
      {searchResults.length > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-2xl p-4 max-w-md mx-auto my-4 shadow-2xl z-30">
          <h3 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Kết quả tìm kiếm học sinh</h3>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {searchResults.map((st) => (
              <div
                key={st.user_id}
                onClick={() => handleSelectStudentFromSearch(st.user_id)}
                className="p-3 bg-dark-bg border border-dark-border hover:border-brand-blue rounded-xl cursor-pointer transition-all flex items-center justify-between"
              >
                <div>
                  <h4 className="text-sm font-medium text-slate-200">{st.name}</h4>
                  <span className="text-xs text-slate-400">{st.username} • {st.problem_count} bài nộp</span>
                </div>
                <span className="text-xs font-mono font-semibold text-brand-blue">{st.points} pts</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {activeTab === 'student' ? (
          <StudentDashboard studentId={selectedStudentId} />
        ) : (
          <TeacherDashboard onSelectStudent={(id) => handleSelectStudentFromSearch(id)} />
        )}
      </main>
    </div>
  );
}

export default App;
