export interface ChipProps {
  icon?: string;
  /** Solid ink fill + white text. */
  active?: boolean;
  children?: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export declare function Chip(props: ChipProps): JSX.Element;
export interface StarterChipProps { icon?: string; children?: React.ReactNode; onClick?: () => void; style?: React.CSSProperties }
export declare function StarterChip(props: StarterChipProps): JSX.Element;
