export interface BrandMarkProps {
  /** header = 30px gem + 14px name; splash = 96px gem with 34px name beneath. */
  size?: 'header' | 'splash';
  title?: string;
  showTitle?: boolean;
  style?: React.CSSProperties;
}
export declare function BrandMark(props: BrandMarkProps): JSX.Element;
