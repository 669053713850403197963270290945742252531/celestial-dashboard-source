// -----------------------------
// Inject CSS
// -----------------------------
const notifStyles = `
/* Toasts */
#toast-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  left: 1rem;
  max-width: calc(100vw - 2rem);
  display: flex;
  flex-direction: column;
  align-items: flex-end;  /* toasts still right-align within the container */
  z-index: 9999;
  pointer-events: none;
}
.toast {
  margin-bottom: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  backdrop-filter: blur(12px);
  background: rgba(20, 20, 25, 0.6);
  color: white;
  box-shadow: 0 0 20px rgba(0,0,0,0.4);
  font-size: 0.9rem;
  opacity: 0;
  transform: translateY(-10px);
  cursor: pointer;
  overflow: hidden;

  transition: 
    opacity 0.25s ease,
    transform 0.25s ease,
    height 0.25s ease,
    margin 0.25s ease,
    padding 0.25s ease;
}
.toast.show {
  opacity: 1;
  transform: translateY(0);
}
.toast.removing {
  height: 0 !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  margin-bottom: 0 !important;
  opacity: 0;
  transform: translateY(-10px);
}
.toast-success { border-left: 4px solid #3aff84; }
.toast-info { border-left: 4px solid #64c8ff; }
.toast-error { border-left: 4px solid #ff4e4e; }

/* Dialog */
#ui-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.65);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  opacity: 0;
  transition: opacity 0.25s ease;
}
#ui-dialog-overlay.show {
  opacity: 1;
}
#ui-dialog-box {
  background: rgba(25,25,30,0.85);
  padding: 1.5rem;
  border-radius: 1rem;
  width: 320px;
  text-align: center;
  color: white;
  box-shadow: 0 0 25px rgba(0,0,0,0.45);
  transform: scale(0.95);
  transition: transform 0.25s ease, opacity 0.25s ease;
  opacity: 0;
}
#ui-dialog-overlay.show #ui-dialog-box {
  transform: scale(1);
  opacity: 1;
}
#ui-dialog-buttons {
  margin-top: 1rem;
  display: flex;
  justify-content: center;
  gap: 1rem;
}
.dialog-btn {
  position: relative;
  overflow: hidden;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  cursor: pointer;
  border: none;
  background: rgba(255,255,255,0.1);
  color: white;
  transition: 0.2s;
}
.dialog-btn:hover { background: rgba(255,255,255,0.2); }
.dialog-btn-yes { border: 1px solid #3aff84; }
.dialog-btn-no { border: 1px solid #ff4e4e; }

/* Ripple effect */
.ripple {
  position: absolute;
  border-radius: 50%;
  transform: scale(0);
  animation: ripple 0.6s linear;
  pointer-events: none;
}
@keyframes ripple {
  to { transform: scale(4); opacity: 0; }
}
`;

const styleTag = document.createElement('style');
styleTag.textContent = notifStyles;
document.head.appendChild(styleTag);

// -----------------------------
// Toast System
// -----------------------------
const MAX_TOASTS = 20;

export function createToast(message, type = "info", duration = 3) {
  const durationMs = duration * 1000;

  // Create container if missing
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.style.position = "fixed";
    container.style.top = "1rem";
    container.style.right = "1rem";
    container.style.left = "1rem";
    container.style.maxWidth = "calc(100vw - 2rem)";  // replace the 350px
    container.style.alignItems = "flex-end";

    container.style.display = "flex";
    container.style.flexDirection = "column";
    document.body.appendChild(container);
  }

  // If too many toasts, remove the oldest
  const currentToasts = container.querySelectorAll(".toast");
  if (currentToasts.length >= MAX_TOASTS) {
    const oldest = currentToasts[0];
    oldest && oldest.remove();
  }

  // Create toast element
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  // Proper independent sizing
  toast.style.display = "block";           // sizes horizontally naturally
  toast.style.maxWidth = "350px";          // wrap only if too long
  toast.style.whiteSpace = "normal";       // allow wrapping
  toast.style.wordBreak = "break-word";
  toast.style.padding = "0.75rem 1rem";
  toast.style.borderRadius = "0.75rem";
  toast.style.background = "rgba(20, 20, 25, 0.6)";
  toast.style.color = "white";
  toast.style.boxShadow = "0 0 20px rgba(0,0,0,0.4)";
  toast.style.opacity = "0";
  toast.style.transform = "translateY(-10px)";
  toast.style.alignSelf = "flex-end"; // align each toast to the right
  toast.style.width = "auto";
  toast.style.pointerEvents = "auto";      // click-to-close
  toast.style.position = "relative";

  container.appendChild(toast);

  // Measure full height AFTER appending
  const fullHeight = toast.offsetHeight;

  // Start collapsed
  toast.style.height = "0px";
  toast.style.paddingTop = "0px";
  toast.style.paddingBottom = "0px";
  toast.style.opacity = "0";
  toast.style.transform = "translateY(-10px)";

  // Animate in on next frame
  requestAnimationFrame(() => {
    toast.style.height = fullHeight + "px";
    toast.style.paddingTop = "0.75rem";
    toast.style.paddingBottom = "0.75rem";
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  });

  // Remove function
  const removeToast = () => {
    toast.style.height = "0px";
    toast.style.paddingTop = "0px";
    toast.style.paddingBottom = "0px";
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-10px)";
    toast.style.marginBottom = "0px";

    clearTimeout(timeoutId);

    setTimeout(() => toast.remove(), 250);
  };

  // Auto-remove
  const timeoutId = setTimeout(removeToast, durationMs);

  // Click-to-close
  toast.addEventListener("click", removeToast);
}





// -----------------------------
// Dialog System
// -----------------------------
export function createDialog(message) {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.id = 'ui-dialog-overlay';

        const dialog = document.createElement('div');
        dialog.id = 'ui-dialog-box';
        dialog.innerHTML = `
          <p>${message}</p>
          <div id="ui-dialog-buttons">
            <button class="dialog-btn dialog-btn-yes">Yes</button>
            <button class="dialog-btn dialog-btn-no">No</button>
          </div>
        `;

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        // Animate in
        void overlay.offsetWidth;
        overlay.classList.add('show');

        const btnYes = dialog.querySelector('.dialog-btn-yes');
        const btnNo = dialog.querySelector('.dialog-btn-no');

        addRippleEffect(btnYes, '58,255,132');
        addRippleEffect(btnNo, '255,78,78');

        const closeDialog = () => {
            overlay.classList.remove('show');
            setTimeout(() => overlay.remove(), 300);
            document.removeEventListener('keydown', handleEscape);
        };

        const handleEscape = (e) => { if(e.key === 'Escape') { closeDialog(); resolve(false); } };
        document.addEventListener('keydown', handleEscape);

        btnYes.addEventListener('click', () => { closeDialog(); resolve(true); });
        btnNo.addEventListener('click', () => { closeDialog(); resolve(false); });
    });
}

// -----------------------------
// Ripple Effect
// -----------------------------
function addRippleEffect(button, color = '255,255,255') {
  button.addEventListener('click', e => {
    if (button.disabled) return;

    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    ripple.style.background = `rgba(${color},0.3)`;

    const rect = button.getBoundingClientRect();
    ripple.style.left = `${e.clientX - rect.left}px`;
    ripple.style.top = `${e.clientY - rect.top}px`;
    ripple.style.width = ripple.style.height = `${Math.max(rect.width, rect.height)}px`;

    button.appendChild(ripple);

    ripple.addEventListener('animationend', () => ripple.remove());
  });
}
