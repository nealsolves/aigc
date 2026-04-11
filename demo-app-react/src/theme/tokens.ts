export const IBM_COLORS = {
  blue60:     '#0f62fe',
  blue40:     '#78a9ff',
  cyan30:     '#82cfff',
  teal30:     '#3ddbd9',
  teal60:     '#007d79',
  magenta40:  '#ff7eb6',
  purple40:   '#be95ff',
  green40:    '#42be65',
  orange40:   '#ff832b',
  red40:      '#ff8389',
  black:      '#000000',
  white:      '#ffffff',
  coolGray10: '#f2f4f8',
  coolGray30: '#c1c7cd',
} as const

export type IBMColor = keyof typeof IBM_COLORS

/** Map a lab number (1–10) to its IBM accent color */
export const LAB_COLORS: Record<number, string> = {
  1:  IBM_COLORS.blue60,
  2:  IBM_COLORS.magenta40,
  3:  IBM_COLORS.teal30,
  4:  IBM_COLORS.purple40,
  5:  IBM_COLORS.cyan30,
  6:  IBM_COLORS.teal60,
  7:  IBM_COLORS.blue40,
  8:  IBM_COLORS.green40,
  9:  IBM_COLORS.orange40,
  10: IBM_COLORS.red40,
}
