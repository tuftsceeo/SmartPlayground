/**
 * Playground Control App - Python Bridge
 */

export const PyBridge = {
  async call(functionName, ...args) {
    console.log(`PyBridge.call: ${functionName}`, args);
    
    return Promise.race([
      new Promise((resolve) => {
        const callbackName = `__pycallback_${functionName}_${Date.now()}`;
        window[callbackName] = (result) => {
          console.log(`PyBridge callback received for ${functionName}:`, result);
          resolve(result);
          delete window[callbackName];
        };
        window.dispatchEvent(new CustomEvent('py-call', {
          detail: { 
            function: functionName, 
            args: JSON.stringify(args), 
            callback: callbackName 
          }
        }));
      }),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('PyBridge timeout')), 5000)
      )
    ]);
  },
  
  on(eventName, callback) {
    window.addEventListener(`py-${eventName}`, (e) => callback(e.detail));
  }
};