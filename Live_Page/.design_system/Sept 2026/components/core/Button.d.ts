/**
 * @startingPoint section="Core" subtitle="Filled gradient and outline actions" viewport="700x200"
 */
export interface ButtonProps {
  /** primary = pink gradient CTA; secondary = white outline; teal = confirm/connect;
   *  connect = header-sized teal pill; send = footer "Send to Box" pill. */
  variant?: 'primary' | 'secondary' | 'teal' | 'connect' | 'send';
  /** compact shrinks secondary buttons to the 11px inline size used in My Box. */
  size?: 'default' | 'compact';
  /** Icon name rendered before the label. */
  icon?: string;
  /** Icon name rendered after the label. */
  iconAfter?: string;
  /** Stretch to 100% — the default shape inside overlay cards. */
  fullWidth?: boolean;
  disabled?: boolean;
  /** connect variant only: swaps the teal gradient for the grey "already connected" one. */
  connected?: boolean;
  children?: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export declare function Button(props: ButtonProps): JSX.Element;
