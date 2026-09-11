export interface IconButtonProps {
  /** Icon name; ignored when `glyph` is set. */
  icon?: string;
  /** Literal text glyph instead of an icon — the app uses "</>" for Show code. */
  glyph?: string;
  /** Pink-tinted selected state. */
  active?: boolean;
  size?: number;
  title?: string;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export declare function IconButton(props: IconButtonProps): JSX.Element;
export interface SendButtonProps { onClick?: () => void; style?: React.CSSProperties }
export declare function SendButton(props: SendButtonProps): JSX.Element;
