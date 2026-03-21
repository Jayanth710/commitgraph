"use client";
import { createContext, useContext, useEffect, useState } from "react";

type AccountFilterContextType = {
  activeAccountId: string | null;
  setActiveAccountId: (accountId: string | null) => void;
};

const AccountFilterContext = createContext<AccountFilterContextType>({
  activeAccountId: null,
  setActiveAccountId: () => {},
});

const STORAGE_KEY = "commitgraph_active_account_id";

export function useAccountFilter() {
  return useContext(AccountFilterContext);
}

export function AccountFilterProvider({ children }: { children: React.ReactNode }) {
  const [activeAccountId, setActiveAccountIdState] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    setActiveAccountIdState(saved || null);
  }, []);

  const setActiveAccountId = (accountId: string | null) => {
    setActiveAccountIdState(accountId);
    if (accountId) {
      localStorage.setItem(STORAGE_KEY, accountId);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    window.dispatchEvent(new Event("commitgraph:account-filter-changed"));
  };

  return (
    <AccountFilterContext.Provider value={{ activeAccountId, setActiveAccountId }}>
      {children}
    </AccountFilterContext.Provider>
  );
}