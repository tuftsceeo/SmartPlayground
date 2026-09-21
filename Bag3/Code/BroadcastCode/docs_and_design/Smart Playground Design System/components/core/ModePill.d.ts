export interface ModePillProps {
  /** serve = mint (handing out code), write = lilac (writing tags), muted = idle/disabled. */
  tone?: 'serve' | 'write' | 'muted';
  icon?: string;
  children?: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export declare function ModePill(props: ModePillProps): JSX.Element;
export interface ConnChipProps { tone?: 'error' | 'sending' | 'repl'; children?: React.ReactNode; style?: React.CSSProperties }
export declare function ConnChip(props: ConnChipProps): JSX.Element;
export interface SsidChipProps { children?: React.ReactNode; style?: React.CSSProperties }
export declare function SsidChip(props: SsidChipProps): JSX.Element;
export interface TagBadgeProps { children?: React.ReactNode; style?: React.CSSProperties }
export declare function TagBadge(props: TagBadgeProps): JSX.Element;
