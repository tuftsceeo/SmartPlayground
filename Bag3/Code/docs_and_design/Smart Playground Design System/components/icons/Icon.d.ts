export interface IconProps {
  /** Icon name from the ChatBroadcast set, e.g. "wand", "cable", "send". */
  name: string;
  /** Pixel size (square). Product uses 12–46. */
  size?: number;
  /** Stroke width. Brand default 1.8; 1.3 for oversized empty-state glyphs. */
  strokeWidth?: number;
  /** Overrides currentColor. */
  color?: string;
  /** Accessible label; omit for decorative icons. */
  title?: string;
  style?: React.CSSProperties;
  className?: string;
}
export declare function Icon(props: IconProps): JSX.Element | null;
export declare const ICON_NAMES: string[];
export declare const ICON_PATHS: Record<string, string>;
export declare function categoryIcon(category: string): string;
