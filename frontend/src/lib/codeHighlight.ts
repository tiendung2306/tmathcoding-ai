import hljs from 'highlight.js/lib/core';
import 'highlight.js/styles/github-dark.css';
import c from 'highlight.js/lib/languages/c';
import cpp from 'highlight.js/lib/languages/cpp';
import csharp from 'highlight.js/lib/languages/csharp';
import delphi from 'highlight.js/lib/languages/delphi';
import go from 'highlight.js/lib/languages/go';
import java from 'highlight.js/lib/languages/java';
import javascript from 'highlight.js/lib/languages/javascript';
import kotlin from 'highlight.js/lib/languages/kotlin';
import php from 'highlight.js/lib/languages/php';
import python from 'highlight.js/lib/languages/python';
import ruby from 'highlight.js/lib/languages/ruby';
import rust from 'highlight.js/lib/languages/rust';
import swift from 'highlight.js/lib/languages/swift';
import typescript from 'highlight.js/lib/languages/typescript';

hljs.registerLanguage('c', c);
hljs.registerLanguage('cpp', cpp);
hljs.registerLanguage('csharp', csharp);
hljs.registerLanguage('delphi', delphi);
hljs.registerLanguage('go', go);
hljs.registerLanguage('java', java);
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('kotlin', kotlin);
hljs.registerLanguage('php', php);
hljs.registerLanguage('python', python);
hljs.registerLanguage('ruby', ruby);
hljs.registerLanguage('rust', rust);
hljs.registerLanguage('swift', swift);
hljs.registerLanguage('typescript', typescript);

export function resolveSourceLanguage(name: string): string | null {
  const value = name.trim().toLowerCase();
  if (value.includes('c++') || value.includes('cpp') || value.includes('g++') || value.includes('gnu++')) return 'cpp';
  if (value.includes('python') || value.includes('pypy') || /^py\d/.test(value)) return 'python';
  if (value.includes('typescript') || value === 'ts') return 'typescript';
  if (value.includes('javascript') || value.includes('node.js') || value === 'js') return 'javascript';
  if (value.includes('c#') || value.includes('csharp')) return 'csharp';
  if (value === 'c' || /^c\d+/.test(value) || /^gnu c(?:\d|$)/.test(value)) return 'c';
  if (value.includes('pascal') || value.includes('delphi')) return 'delphi';
  if (value === 'go' || value.startsWith('go ') || value.includes('golang')) return 'go';
  for (const language of ['java', 'kotlin', 'rust', 'ruby', 'swift', 'php']) {
    if (value.includes(language)) return language;
  }
  return null;
}

export function highlightSource(code: string, languageName: string): string | null {
  const language = resolveSourceLanguage(languageName);
  if (!language) return null;
  try {
    return hljs.highlight(code, { language, ignoreIllegals: true }).value;
  } catch {
    return null;
  }
}
