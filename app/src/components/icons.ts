/**
 * 图标集中导入（豆包风格 SVG）
 *
 * 所有 SVG 来自项目根 /icons 目录，Lucide 风格，内置主色 #0065fd / 文本色 #0e1115。
 * Vite 会按 assetsInlineLimit 自动内联为 data URL（CSP 允许 img-src data:）。
 */
import rotateCcw from "../../../icons/rotate-ccw.svg";
import clipboardCopy from "../../../icons/clipboard-copy.svg";
import scissors from "../../../icons/scissors.svg";
import mousePointerClick from "../../../icons/mouse-pointer-click.svg";
import mail from "../../../icons/mail.svg";
import arrowDownToLine from "../../../icons/arrow-down-to-line.svg";
import folderColor from "../../../icons/folder-color.svg";
import imageIcon from "../../../icons/image.svg";
import palette from "../../../icons/palette.svg";
import info from "../../../icons/info.svg";
import alertTriangle from "../../../icons/alert-triangle.svg";
import check from "../../../icons/check.svg";
import scissorsMuted from "../../../icons/scissors-muted.svg";
import compress from "../../../icons/compress.svg";

export const Icon = {
  rotateCcw,
  clipboardCopy,
  scissors,
  scissorsMuted,
  mousePointerClick,
  mail,
  arrowDownToLine,
  folderColor,
  image: imageIcon,
  palette,
  info,
  alertTriangle,
  check,
  compress,
} as const;

export type IconKey = keyof typeof Icon;
