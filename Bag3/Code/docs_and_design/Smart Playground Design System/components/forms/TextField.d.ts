export interface TextFieldProps {
  /** Uppercase 11px caps label above the field. */
  label?: string;
  /** Shows the pencil affordance inside the right edge (means "you can rename this"). */
  pencil?: boolean;
  /** Red helper text under the field. */
  error?: string;
  /** Product default is centred text. */
  centered?: boolean;
  placeholder?: string;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  maxLength?: number;
  style?: React.CSSProperties;
}
export declare function TextField(props: TextFieldProps): JSX.Element;
export interface SearchInputProps { placeholder?: string; value?: string; onChange?: (e: any) => void; style?: React.CSSProperties }
export declare function SearchInput(props: SearchInputProps): JSX.Element;
export interface ChatInputProps { placeholder?: string; value?: string; onChange?: (e: any) => void; onKeyDown?: (e: any) => void; style?: React.CSSProperties }
export declare function ChatInput(props: ChatInputProps): JSX.Element;
