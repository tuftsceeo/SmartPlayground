export interface ToastProps { error?: boolean; children?: React.ReactNode; style?: React.CSSProperties }
export declare function Toast(props: ToastProps): JSX.Element;
export interface ConnectToastProps { children?: React.ReactNode; style?: React.CSSProperties }
export declare function ConnectToast(props: ConnectToastProps): JSX.Element;
export interface SentBannerProps { children?: React.ReactNode; style?: React.CSSProperties }
export declare function SentBanner(props: SentBannerProps): JSX.Element;
export interface ProgressBarProps { /** 0–100 */ value?: number; label?: string; style?: React.CSSProperties }
export declare function ProgressBar(props: ProgressBarProps): JSX.Element;
export interface TagBarsProps { total: number; done: number; style?: React.CSSProperties }
export declare function TagBars(props: TagBarsProps): JSX.Element;
export interface TagRowProps { state?: 'idle' | 'next' | 'done'; name: string; status?: string; style?: React.CSSProperties }
export declare function TagRow(props: TagRowProps): JSX.Element;
export interface RequirementRowProps { icon: string; children?: React.ReactNode; style?: React.CSSProperties }
export declare function RequirementRow(props: RequirementRowProps): JSX.Element;
