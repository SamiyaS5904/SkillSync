// ========== Utility Functions ==========
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ========== Smooth Scrolling ==========
function scrollToSection(sectionId) {
    const element = document.getElementById(sectionId);
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// ========== Intersection Observer for Animations ==========
function createObserver() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                
                // Add staggered animation for feature cards
                if (entry.target.classList.contains('feature-card')) {
                    const cards = document.querySelectorAll('.feature-card');
                    cards.forEach((card, index) => {
                        if (card === entry.target) {
                            card.style.animationDelay = `${index * 0.2}s`;
                        }
                    });
                }
            }
        });
    }, observerOptions);

    // Observe elements
    const elementsToObserve = document.querySelectorAll(
        '.feature-card, .ai-content, .footer'
    );
    
    elementsToObserve.forEach(el => observer.observe(el));
}

// ========== Dynamic Background Effects ==========
function createParallaxEffect() {
    const bgOrbs = document.querySelectorAll('.bg-orb');
    
    const handleMouseMove = debounce((e) => {
        const { clientX, clientY } = e;
        const { innerWidth, innerHeight } = window;
        
        const xPercent = (clientX / innerWidth - 0.5) * 2;
        const yPercent = (clientY / innerHeight - 0.5) * 2;
        
        bgOrbs.forEach((orb, index) => {
            const speed = (index + 1) * 0.5;
            const x = xPercent * speed * 10;
            const y = yPercent * speed * 10;
            
            orb.style.transform = `translate(${x}px, ${y}px)`;
        });
    }, 16);

    document.addEventListener('mousemove', handleMouseMove);
}

// ========== Feature Card Interactions ==========
function initFeatureCards() {
    const featureCards = document.querySelectorAll('.feature-card');
    
    featureCards.forEach(card => {
        // Enhanced hover effect
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-12px) scale(1.03)';
            
            // Add subtle rotation based on mouse position
            card.addEventListener('mousemove', handleCardMouseMove);
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0) scale(1) rotateX(0) rotateY(0)';
            card.removeEventListener('mousemove', handleCardMouseMove);
        });
        
        // Click interaction
        card.addEventListener('click', () => {
            const feature = card.dataset.feature;
            handleFeatureClick(feature);
        });
    });
}

function handleCardMouseMove(e) {
    const card = e.currentTarget;
    const rect = card.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    
    const rotateX = (e.clientY - centerY) / 10;
    const rotateY = (centerX - e.clientX) / 10;
    
    card.style.transform = `translateY(-12px) scale(1.03) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
}

function handleFeatureClick(feature) {
    // Create ripple effect
    createRippleEffect(event);
    
    // Simulate navigation (you can replace with actual routing)
    console.log(`Navigating to ${feature} section`);
    
    // Show a toast notification
    showNotification(`Exploring ${feature}...`, 'info');
}

// ========== Ripple Effect ==========
function createRippleEffect(e) {
    const button = e.currentTarget;
    const ripple = document.createElement('span');
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    
    ripple.style.cssText = `
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.3);
        transform: scale(0);
        animation: ripple 0.6s linear;
        width: ${size}px;
        height: ${size}px;
        left: ${x}px;
        top: ${y}px;
        pointer-events: none;
    `;
    
    button.style.position = 'relative';
    button.style.overflow = 'hidden';
    button.appendChild(ripple);
    
    setTimeout(() => {
        ripple.remove();
    }, 600);
}

// ========== AI Assistant Interactions ==========
function initAIAssistant() {
    const aiButton = document.getElementById('ai-cta');
    
    if (aiButton) {
        aiButton.addEventListener('click', (e) => {
            createRippleEffect(e);
            handleAIButtonClick();
        });
        
        // Add floating animation on hover
        aiButton.addEventListener('mouseenter', () => {
            aiButton.style.animation = 'none';
            aiButton.style.transform = 'translateY(-4px) scale(1.05)';
        });
        
        aiButton.addEventListener('mouseleave', () => {
            aiButton.style.animation = 'pulse-glow 2s ease-in-out infinite';
            aiButton.style.transform = 'translateY(0) scale(1)';
        });
    }
}

function handleAIButtonClick() {
    // Simulate AI assistant activation
    showNotification('🤖 AI Assistant is starting...', 'success');
    
    // Add some interactive feedback
    setTimeout(() => {
        showNotification('✨ Ready to help with your career!', 'success');
    }, 1500);
}

// ========== Notification System ==========
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Style the notification
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'hsl(142, 76%, 36%)' : 'hsl(217, 91%, 60%)'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.3);
        z-index: 1000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        max-width: 300px;
        font-weight: 500;
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);
    
    // Remove after delay
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// ========== Scroll Progress Indicator ==========
function createScrollProgress() {
    const progressBar = document.createElement('div');
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0%;
        height: 3px;
        background: linear-gradient(90deg, hsl(262, 83%, 58%), hsl(217, 91%, 60%), hsl(174, 72%, 56%));
        z-index: 1000;
        transition: width 0.1s ease;
    `;
    
    document.body.appendChild(progressBar);
    
    const updateProgress = debounce(() => {
        const scrollTop = window.pageYOffset;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = (scrollTop / docHeight) * 100;
        progressBar.style.width = scrollPercent + '%';
    }, 10);
    
    window.addEventListener('scroll', updateProgress);
}

// ========== Performance Monitoring ==========
function initPerformanceOptimizations() {
    // Lazy load images if any
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        imageObserver.unobserve(img);
                    }
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
    
    // Prefetch critical resources
    const prefetchLinks = [
        'https://fonts.gstatic.com',
    ];
    
    prefetchLinks.forEach(url => {
        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = url;
        document.head.appendChild(link);
    });
}

// ========== Error Handling ==========
function initErrorHandling() {
    window.addEventListener('error', (e) => {
        console.error('JavaScript Error:', e.error);
        // You could send this to an analytics service
    });
    
    window.addEventListener('unhandledrejection', (e) => {
        console.error('Unhandled Promise Rejection:', e.reason);
        e.preventDefault();
    });
}

// ========== Add CSS for dynamic animations ==========
function addDynamicStyles() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        
        .animate-in {
            animation: slideInUp 0.8s ease forwards;
        }
        
        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .notification {
            font-family: var(--font-family);
        }
        
        /* Enhanced focus styles for better accessibility */
        .btn:focus-visible {
            outline: 3px solid hsl(262, 83%, 58%);
            outline-offset: 2px;
        }
    `;
    
    document.head.appendChild(style);
}

// ========== Initialization ==========
function init() {
    // Wait for DOM to be fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
        return;
    }
    
    try {
        // Initialize all features
        addDynamicStyles();
        createObserver();
        createParallaxEffect();
        initFeatureCards();
        initAIAssistant();
        createScrollProgress();
        initPerformanceOptimizations();
        initErrorHandling();
        
        // Show welcome message
        setTimeout(() => {
            showNotification('🚀 Welcome to SkillSync!', 'info');
        }, 1000);
        
        console.log('SkillSync initialized successfully!');
        
    } catch (error) {
        console.error('Initialization error:', error);
    }
}

// ========== Global Functions ==========
// Make scrollToSection available globally for inline onclick handlers
window.scrollToSection = scrollToSection;

// Start the application
init();

// ========== Analytics & Performance Tracking ==========
// Basic performance tracking
window.addEventListener('load', () => {
    if ('performance' in window) {
        const perfData = performance.getEntriesByType('navigation')[0];
        console.log('Page Load Time:', perfData.loadEventEnd - perfData.loadEventStart, 'ms');
        
        // Track Core Web Vitals if supported
        if ('PerformanceObserver' in window) {
            try {
                const observer = new PerformanceObserver((list) => {
                    list.getEntries().forEach((entry) => {
                        console.log(`${entry.name}: ${entry.value}ms`);
                    });
                });
                
                observer.observe({ entryTypes: ['measure', 'mark'] });
            } catch (e) {
                // PerformanceObserver not fully supported
            }
        }
    }
});

// Track user engagement
let engagementStartTime = Date.now();
let isPageVisible = true;

document.addEventListener('visibilitychange', () => {
    isPageVisible = !document.hidden;
    if (isPageVisible) {
        engagementStartTime = Date.now();
    }
});

window.addEventListener('beforeunload', () => {
    if (isPageVisible) {
        const engagementTime = Date.now() - engagementStartTime;
        console.log('Engagement time:', Math.round(engagementTime / 1000), 'seconds');
    }
});