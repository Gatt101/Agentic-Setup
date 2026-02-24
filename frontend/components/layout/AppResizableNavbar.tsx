"use client";

import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "@/components/layout/ThemeToggle";
import {
  MobileNav,
  MobileNavHeader,
  MobileNavMenu,
  MobileNavToggle,
  NavBody,
  Navbar,
  NavbarButton,
  NavbarLogo,
  NavItems,
} from "@/components/ui/resizable-navbar";

function baseNavItems(pathname: string) {
  if (pathname === "/") {
    return [
      { link: "#workflow", name: "Workflow" },
      { link: "#audience", name: "Audience" },
      { link: "#trust", name: "Trust" },
      { link: "#start", name: "Get Started" },
    ];
  }

  return [
    { link: "/", name: "Home" },
    { link: "/sign-in", name: "Log in" },
    { link: "/sign-up", name: "Sign up" },
  ];
}

export function AppResizableNavbar() {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  if (pathname.startsWith("/dashboard") || pathname.startsWith("/select-role")) {
    return null;
  }

  const navItems = baseNavItems(pathname);

  return (
    <Navbar className="pointer-events-none">
      <NavBody className="pointer-events-auto">
        <NavbarLogo href="/" />
        <NavItems items={navItems} />
        <div className="relative z-10 flex items-center gap-2">
          <ThemeToggle />
          <SignedOut>
            <SignInButton forceRedirectUrl="/select-role" mode="redirect">
              <NavbarButton as="button" variant="secondary">
                Login
              </NavbarButton>
            </SignInButton>
            <SignUpButton forceRedirectUrl="/select-role" mode="redirect">
              <NavbarButton as="button" variant="primary">
                Start
              </NavbarButton>
            </SignUpButton>
          </SignedOut>
          <SignedIn>
            <NavbarButton href="/dashboard" variant="primary">
              Dashboard
            </NavbarButton>
            <div className="ml-1 flex items-center">
              <UserButton />
            </div>
          </SignedIn>
        </div>
      </NavBody>

      <MobileNav className="pointer-events-auto">
        <MobileNavHeader>
          <NavbarLogo href="/" />
          <MobileNavToggle
            isOpen={isMobileMenuOpen}
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          />
        </MobileNavHeader>

        <MobileNavMenu
          isOpen={isMobileMenuOpen}
          onClose={() => setIsMobileMenuOpen(false)}
        >
          {navItems.map((item, idx) => (
            <a
              className="relative text-neutral-600 dark:text-neutral-300"
              href={item.link}
              key={`mobile-link-${idx}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              <span className="block">{item.name}</span>
            </a>
          ))}

          <div className="mt-2">
            <ThemeToggle />
          </div>

          <div className="flex w-full flex-col gap-3">
            <SignedOut>
              <SignInButton forceRedirectUrl="/select-role" mode="redirect">
                <NavbarButton
                  as="button"
                  className="w-full"
                  onClick={() => setIsMobileMenuOpen(false)}
                  variant="secondary"
                >
                  Login
                </NavbarButton>
              </SignInButton>
              <SignUpButton forceRedirectUrl="/select-role" mode="redirect">
                <NavbarButton
                  as="button"
                  className="w-full"
                  onClick={() => setIsMobileMenuOpen(false)}
                  variant="primary"
                >
                  Start
                </NavbarButton>
              </SignUpButton>
            </SignedOut>
            <SignedIn>
              <NavbarButton
                className="w-full"
                href="/dashboard"
                onClick={() => setIsMobileMenuOpen(false)}
                variant="primary"
              >
                Dashboard
              </NavbarButton>
            </SignedIn>
          </div>
        </MobileNavMenu>
      </MobileNav>
    </Navbar>
  );
}
