/**
 * @startingPoint section="Surfaces" subtitle="Panels, game cards and overlays" viewport="700x360"
 */
export interface ViewPanelProps { children?: React.ReactNode; style?: React.CSSProperties }
export declare function ViewPanel(props: ViewPanelProps): JSX.Element;
export interface SplashCardProps {
  icon: string; title: string; blurb: string;
  /** Pink gradient fill — at most one per screen. */
  primary?: boolean;
  onClick?: () => void; style?: React.CSSProperties;
}
export declare function SplashCard(props: SplashCardProps): JSX.Element;
export interface ExampleCardProps {
  icon: string; name: string; description: string;
  /** Amber note, e.g. "8 NFC tags". */
  badge?: string;
  actions?: React.ReactNode; onOpen?: () => void; style?: React.CSSProperties;
}
export declare function ExampleCard(props: ExampleCardProps): JSX.Element;
export interface CardActionButtonProps { icon?: string; danger?: boolean; children?: React.ReactNode; onClick?: (e: any) => void; style?: React.CSSProperties }
export declare function CardActionButton(props: CardActionButtonProps): JSX.Element;
export interface OverlayCardProps { width?: number; align?: 'center' | 'left'; children?: React.ReactNode; style?: React.CSSProperties }
export declare function OverlayCard(props: OverlayCardProps): JSX.Element;
export interface OverlayScrimProps { children?: React.ReactNode; style?: React.CSSProperties }
export declare function OverlayScrim(props: OverlayScrimProps): JSX.Element;
