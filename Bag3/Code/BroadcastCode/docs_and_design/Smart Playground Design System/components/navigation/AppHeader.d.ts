/**
 * @startingPoint section="Navigation" subtitle="Brand, pill tabs and header status slot" viewport="700x110"
 */
export interface AppHeaderTab { id: string; label: string }
export interface AppHeaderProps {
  title?: string;
  tabs?: AppHeaderTab[];
  active?: string;
  onTab?: (id: string) => void;
  /** Right-aligned slot: SsidChip, ModePill, ConnChip, connect Button. */
  children?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function AppHeader(props: AppHeaderProps): JSX.Element;
export interface TabBarProps { tabs: AppHeaderTab[]; active?: string; onSelect?: (id: string) => void; style?: React.CSSProperties }
export declare function TabBar(props: TabBarProps): JSX.Element;
