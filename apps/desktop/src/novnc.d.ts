declare module '@novnc/novnc/lib/rfb.js' {
  export default class RFB {
    constructor(target: HTMLElement, url: string, options?: any);
    scaleViewport: boolean;
    clipViewport: boolean;
    resizeSession: boolean;
    addEventListener(event: string, handler: (e: any) => void): void;
    removeEventListener(event: string, handler: (e: any) => void): void;
    disconnect(): void;
    focus?(): void;
  }
}

declare module '@novnc/novnc' {
  export default class RFB {
    constructor(target: HTMLElement, url: string, options?: any);
    scaleViewport: boolean;
    clipViewport: boolean;
    resizeSession: boolean;
    addEventListener(event: string, handler: (e: any) => void): void;
    removeEventListener(event: string, handler: (e: any) => void): void;
    disconnect(): void;
    focus?(): void;
  }
}
