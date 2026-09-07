import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error boundary", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto flex min-h-screen max-w-lg flex-col items-start justify-center gap-4 px-6">
          <p className="text-sm font-medium uppercase tracking-wider text-accent">Something went wrong</p>
          <h1 className="text-2xl font-semibold tracking-tight">Unexpected application error</h1>
          <p className="text-ink-muted">
            {this.state.error.message || "An unknown error occurred while rendering this page."}
          </p>
          <Button
            onClick={() => {
              this.setState({ error: null });
              window.location.assign("/items");
            }}
          >
            Back to items
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
