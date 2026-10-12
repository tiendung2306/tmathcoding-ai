import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/queryClient'
import { router } from './router'
import { startSessionSync } from './services/auth'
import './index.css'

startSessionSync()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} fallbackElement={<p role="status" className="p-6">Đang mở trang...</p>} />
    </QueryClientProvider>
  </React.StrictMode>,
)
