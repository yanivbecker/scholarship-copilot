import { NavLink, Outlet } from 'react-router'

import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Today', end: true },
  { to: '/profile', label: 'Profile', end: false },
  { to: '/scholarships', label: 'Scholarships', end: false },
  { to: '/sources', label: 'Sources', end: false },
  { to: '/stories', label: 'Story bank', end: false },
  { to: '/settings', label: 'Settings', end: false },
]

/** App shell: skip link, header navigation, and the current page. */
export function Layout() {
  return (
    <div className="min-h-svh">
      {/* Keyboard users can jump straight past the navigation (NFR-11). */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>
      <header className="border-b">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="font-semibold">Scholarship Copilot</span>
          <nav aria-label="Main">
            <ul className="flex flex-wrap gap-1">
              {NAV.map((item) => (
                <li key={item.to}>
                  {/* NavLink sets aria-current="page" on the active link. */}
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn(
                        'rounded-md px-3 py-1.5 text-sm whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        isActive
                          ? 'bg-muted font-medium'
                          : 'text-muted-foreground hover:text-foreground',
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
