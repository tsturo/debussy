// Shared icon primitives — pure presentational SVGs with no business logic.

export function GradientAvatar({ initial }: { initial: string }) {
  return (
    <div
      style={{
        width: 28,
        height: 28,
        borderRadius: 9,
        background: 'var(--t-gradient)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        fontWeight: 700,
        fontSize: 13,
        color: 'white',
        letterSpacing: '-0.01em',
        userSelect: 'none',
      }}
    >
      {initial}
    </div>
  )
}

export function ChevronDownIcon({ open }: { open?: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        color: 'var(--t-text-3)',
        flexShrink: 0,
        transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
        transition: 'transform 150ms ease',
      }}
    >
      <path
        d="M2 4l4 4 4-4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function GearIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-text-3)', flexShrink: 0 }}
    >
      <path
        d="M7 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M11.33 7c0-.19-.01-.37-.04-.55l1.2-.93a.3.3 0 0 0 .07-.38l-1.13-1.96a.3.3 0 0 0-.36-.13l-1.41.57a4.1 4.1 0 0 0-.95-.55l-.21-1.5A.3.3 0 0 0 8.2 1H5.8a.3.3 0 0 0-.3.26l-.21 1.5c-.34.14-.66.32-.95.55L2.93 2.74a.3.3 0 0 0-.36.13L1.44 4.83a.3.3 0 0 0 .07.38l1.2.93A3.3 3.3 0 0 0 2.67 7c0 .19.01.37.04.55l-1.2.93a.3.3 0 0 0-.07.38l1.13 1.96c.08.14.24.2.36.13l1.41-.57c.29.23.61.41.95.55l.21 1.5c.04.15.17.26.3.26h2.4c.13 0 .26-.11.3-.26l.21-1.5c.34-.14.66-.32.95-.55l1.41.57c.12.07.28.01.36-.13l1.13-1.96a.3.3 0 0 0-.07-.38l-1.2-.93c.03-.18.04-.36.04-.55Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function PlusPurpleIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-purple)', flexShrink: 0 }}
    >
      <path
        d="M6 1v10M1 6h10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function PencilIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-text-3)', flexShrink: 0 }}
    >
      <path
        d="M8.5 1.5a1.414 1.414 0 0 1 2 2L3.5 10.5l-3 .5.5-3 7.5-6.5Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function TrashIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-error, #e05450)', flexShrink: 0 }}
    >
      <path
        d="M1.5 3h9M4 3V2h4v1M10 3l-.75 7.5h-6.5L2 3"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function CheckIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-teal)', flexShrink: 0 }}
    >
      <path
        d="M2 6l3 3 5-5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
