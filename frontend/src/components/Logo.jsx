import { useId } from 'react'

// WHZ 品牌 Logo：渐变圆角方块 + WHZ 字标
export default function Logo({ size = 40, className = '' }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      style={{ borderRadius: 12, display: 'block' }}
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6C5CE7" />
          <stop offset="100%" stopColor="#00CEC9" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill={`url(#${id})`} />
      <text
        x="32"
        y="43"
        fontFamily="Arial, 'PingFang SC', sans-serif"
        fontSize="25"
        fontWeight="700"
        fill="#fff"
        textAnchor="middle"
        letterSpacing="1"
      >
        WHZ
      </text>
    </svg>
  )
}
