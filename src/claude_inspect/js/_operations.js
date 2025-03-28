({
    /**
     * operations:
     *   - apply_chat()
     *   - put_chat(text: string)
     *   - clear_chat()
     *   - new_chat(project_id: string?)
     */

    apply_chat: function() {
        return new Promise((resolve, reject) => {
            const inputElem = document.querySelector('.ProseMirror p');
            if (!inputElem) {
                reject('Input element not found');
                return;
            }
            
            inputElem.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            
            function check() {
                const inputElem = document.querySelector('.ProseMirror p');
                if (inputElem.textContent === '') {
                    resolve();
                } else {
                    setTimeout(check, 10);
                }
            }
            setTimeout(check, 10);
        });
    },

    put_chat: function(text) {
        return new Promise((resolve, reject) => {
            const inputElem = document.querySelector('.ProseMirror p');
            if (inputElem) {
                inputElem.innerText = text;
                resolve();
            }
            else {
                reject('Input element not found');
            }
        });
    },

    clear_chat: function() {
        return new Promise((resolve, reject) => {
            const inputElem = document.querySelector('.ProseMirror p');
            if (inputElem) {
                inputElem.innerText = '';
                resolve();
            } else {
                reject('Input element not found');
            }
        });
    },

    new_chat: function(project_id) {
        function followLink([elem, timeout = 1000]) {
            console.log(timeout);
            return new Promise((resolve, reject) => {
                if (!elem) {
                    reject('link element not found');
                    return;
                }
                const targetPath = (new URL(elem.href)).pathname;
                const t0 = performance.now();
                function check() {
                    if (location.pathname === targetPath) {
                        resolve(targetPath);
                    } else {
                        const t1 = performance.now();
                        if (t1 - t0 > timeout) {
                            reject(`timeout: ${t1 - t0} / ${timeout}: ${targetPath} / ${location.pathname}`);
                        } else {
                            setTimeout(check, 10);
                        }
                    }
                }
                elem.click();
                setTimeout(check, 10);
            });
        }
        
        if (project_id === void 0 || project_id === null || project_id === '') {
            return new Promise((resolve, reject) => {
                const newChatElem = document.querySelector('a[href="/new"]');
                resolve([newChatElem]);
            }).then(followLink);
        } else {
            return (new Promise((resolve, reject) => {
                const projectElem = document.querySelector(`a[href="/projects"]`);
                resolve([projectElem])
            }))
            .then(followLink)
            .then(() => {
                const uuid = /^[A-Za-z0-9]{8}(-[A-Za-z0-9]{4}){3}-[A-Za-z0-9]{12}$/;
                let targetElem = null;
                if (uuid.test(project_id)) {
                    targetElem = document.querySelector(`a[href="/project/${project_id}"]`);
                } else {
                    const projects = document.querySelectorAll(`a[href^="/project/"] > *:first-child`);
                    targetElem = Array.from(projects).find(elem => elem.textContent.trim() === project_id);
                }
                if (!targetElem) {
                    reject(`project ${project_id} aws not found`);
                    return;
                }
                while (targetElem.tagName !== 'A') {
                    targetElem = targetElem.parentElement;
                }
                if (!targetElem) {
                    reject(`project ${project_id} aws not found`);
                    return;
                }
                return followLink([targetElem]);
            });
        }
    },

})