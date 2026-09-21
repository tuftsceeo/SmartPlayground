export interface ChatMessageProps {
  /** user = pink gradient right-aligned; bot = white outlined left; system = grey note. */
  role?: 'user' | 'bot' | 'system';
  children?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function ChatMessage(props: ChatMessageProps): JSX.Element;
export interface ThinkingDotsProps { style?: React.CSSProperties }
export declare function ThinkingDots(props: ThinkingDotsProps): JSX.Element;
export interface CodeBlockProps { language?: string; actions?: React.ReactNode; children?: React.ReactNode; style?: React.CSSProperties }
export declare function CodeBlock(props: CodeBlockProps): JSX.Element;
