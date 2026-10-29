export interface RoleRailItem { id: string; label: string; icon: string; disabled?: boolean }
export interface RoleRailProps {
  items: RoleRailItem[];
  active?: string;
  onSelect?: (id: string) => void;
  style?: React.CSSProperties;
}
export declare function RoleRail(props: RoleRailProps): JSX.Element;
export interface PaneResizerProps { vertical?: boolean; style?: React.CSSProperties }
export declare function PaneResizer(props: PaneResizerProps): JSX.Element;
