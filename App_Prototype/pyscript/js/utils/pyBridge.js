/**
 * Playground Control App - Python Bridge
 */

export const PyBridge = {
  async call(functionName, ...args) {
    return new Promise((resolve) => {
      const callbackName = `__pycallback_${functionName}_${Date.now()}`;
      window[callbackName] = (result) => {
        resolve(result);
        delete window[callbackName];
      };
      window.dispatchEvent(new CustomEvent('py-call', {
        detail: { function: functionName, args, callback: callbackName }
      }));
    });
  },
  
  on(eventName, callback) {
    window.addEventListener(`py-${eventName}`, (e) => callback(e.detail));
  }
};
