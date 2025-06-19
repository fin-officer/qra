// Documentation Template JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const menuToggle = document.createElement('button');
    menuToggle.className = 'menu-toggle';
    menuToggle.textContent = '☰ Menu';
    document.body.appendChild(menuToggle);
    
    const sidebar = document.querySelector('.sidebar');
    
    menuToggle.addEventListener('click', function() {
        sidebar.classList.toggle('active');
    });
    
    // Close menu when clicking outside
    document.addEventListener('click', function(event) {
        if (!sidebar.contains(event.target) && event.target !== menuToggle) {
            sidebar.classList.remove('active');
        }
    });
    
    // Highlight active navigation link
    const sections = document.querySelectorAll('section');
    const navLinks = document.querySelectorAll('.nav-link');
    
    function highlightNav() {
        let current = '';
        
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            
            if (pageYOffset >= sectionTop - 100) {
                current = '#' + section.getAttribute('id');
            }
        });
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === current) {
                link.classList.add('active');
            }
        });
    }
    
    window.addEventListener('scroll', highlightNav);
    highlightNav(); // Initial call
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                // Close mobile menu if open
                sidebar.classList.remove('active');
                
                window.scrollTo({
                    top: targetElement.offsetTop - 80,
                    behavior: 'smooth'
                });
                
                // Update URL without page jump
                if (history.pushState) {
                    history.pushState(null, null, targetId);
                } else {
                    location.hash = targetId;
                }
            }
        });
    });
    
    // Search functionality
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    
    if (searchInput && searchButton) {
        function performSearch() {
            const query = searchInput.value.toLowerCase().trim();
            if (!query) return;
            
            // Simple search implementation
            // In a real app, you might want to use a more sophisticated search
            const allText = document.body.innerText.toLowerCase();
            const matches = allText.includes(query);
            
            if (matches) {
                // Scroll to first occurrence
                const regex = new RegExp(query, 'gi');
                const textNodes = [];
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                
                let node;
                while (node = walker.nextNode()) {
                    if (node.nodeValue.toLowerCase().includes(query)) {
                        textNodes.push(node);
                    }
                }
                
                if (textNodes.length > 0) {
                    // Highlight all occurrences
                    textNodes.forEach(textNode => {
                        const span = document.createElement('span');
                        span.className = 'search-highlight';
                        span.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                        
                        const text = textNode.nodeValue;
                        const newText = document.createTextNode('');
                        let lastIndex = 0;
                        let match;
                        
                        while ((match = regex.exec(text)) !== null) {
                            // Add text before match
                            newText.nodeValue += text.substring(lastIndex, match.index);
                            
                            // Create highlight span for match
                            const highlight = document.createElement('span');
                            highlight.className = 'search-match';
                            highlight.style.backgroundColor = 'rgba(255, 255, 0, 0.5)';
                            highlight.textContent = match[0];
                            
                            // Append highlight to new text
                            newText.nodeValue += '\u200B'; // Zero-width space to separate text nodes
                            newText.parentNode.insertBefore(highlight, newText.nextSibling);
                            
                            lastIndex = match.index + match[0].length;
                        }
                        
                        // Add remaining text
                        newText.nodeValue += text.substring(lastIndex);
                        
                        // Replace original text node with new content
                        textNode.parentNode.replaceChild(newText, textNode);
                        
                        // Scroll to first match
                        if (textNodes[0] === textNode) {
                            setTimeout(() => {
                                highlight.scrollIntoView({
                                    behavior: 'smooth',
                                    block: 'center'
                                });
                            }, 100);
                        }
                    });
                } else {
                    alert('Nie znaleziono wyników dla: ' + query);
                }
            } else {
                alert('Nie znaleziono wyników dla: ' + query);
            }
        }
        
        searchButton.addEventListener('click', performSearch);
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    }
    
    // Add copy button to code blocks
    document.querySelectorAll('pre').forEach(pre => {
        // Create copy button
        const button = document.createElement('button');
        button.className = 'copy-button';
        button.textContent = 'Kopiuj';
        button.style.cssText = `
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            padding: 0.25rem 0.5rem;
            background: #f1f3f4;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.8rem;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.3s, background 0.2s;
        `;
        
        pre.style.position = 'relative';
        pre.appendChild(button);

        // Show/hide button on hover
        pre.addEventListener('mouseenter', () => {
            button.style.opacity = '1';
        });

        pre.addEventListener('mouseleave', () => {
            if (button.textContent !== 'Skopiowano!') {
                button.style.opacity = '0';
            }
        });

        // Copy code on button click
        button.addEventListener('click', () => {
            const code = pre.querySelector('code')?.innerText || pre.innerText;
            navigator.clipboard.writeText(code).then(() => {
                const originalText = button.textContent;
                button.textContent = 'Skopiowano!';
                button.style.background = '#4caf50';
                button.style.color = 'white';
                button.style.borderColor = '#4caf50';
                button.style.opacity = '1';
                
                setTimeout(() => {
                    button.textContent = originalText;
                    button.style.background = '';
                    button.style.color = '';
                    button.style.borderColor = '';
                    button.style.opacity = '0';
                }, 2000);
            });
        });
    });
    
    // Responsive table of contents
    const generateTOC = () => {
        const toc = document.createElement('div');
        toc.className = 'toc';
        toc.innerHTML = '<h3>Spis treści</h3><ul></ul>';
        
        const tocList = toc.querySelector('ul');
        const headings = document.querySelectorAll('h2, h3');
        
        if (headings.length > 2) { // Only add TOC if there are enough headings
            let currentLevel = 2; // Start with h2
            
            headings.forEach(heading => {
                const level = parseInt(heading.tagName.substring(1));
                
                // Add ID if not exists
                if (!heading.id) {
                    heading.id = heading.textContent.toLowerCase()
                        .replace(/[^\w\s]/g, '')
                        .replace(/\s+/g, '-');
                }
                
                const listItem = document.createElement('li');
                listItem.className = `toc-level-${level}`;
                
                const link = document.createElement('a');
                link.href = `#${heading.id}`;
                link.textContent = heading.textContent;
                
                listItem.appendChild(link);
                tocList.appendChild(listItem);
            });
            
            // Insert TOC after first h1 or at the beginning of the content
            const firstHeading = document.querySelector('h1') || document.querySelector('h2');
            if (firstHeading) {
                firstHeading.parentNode.insertBefore(toc, firstHeading.nextSibling);
            } else {
                document.querySelector('main').prepend(toc);
            }
        }
    };
    
    generateTOC();
});
