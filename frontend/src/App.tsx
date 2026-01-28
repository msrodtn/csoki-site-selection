import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StoreMap } from './components/Map/StoreMap';
import { Sidebar } from './components/Sidebar/Sidebar';
import { PasswordGate } from './components/Auth/PasswordGate';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PasswordGate>
        <div className="flex h-screen w-screen overflow-hidden">
          <Sidebar />
          <main className="flex-1 relative">
            <StoreMap />
          </main>
        </div>
      </PasswordGate>
    </QueryClientProvider>
  );
}

export default App;
