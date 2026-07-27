import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/dashboard/AppShell";
import { ProgrammingCard } from "@/components/dashboard/cards/ProgrammingCard";
import { SpotifyCards } from "@/components/dashboard/cards/SpotifyCard";
import { SystemHealthCard } from "@/components/dashboard/cards/SystemHealthCard";
import { TimerCard } from "@/components/dashboard/cards/TimerCard";
import Overview from "@/pages/Overview";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Overview />} />
        <Route path="/programming" element={<ProgrammingCard />} />
        <Route path="/timer" element={<TimerCard />} />
        <Route path="/system-health" element={<SystemHealthCard />} />
        <Route path="/spotify" element={<SpotifyCards />} />
      </Route>
    </Routes>
  );
}

export default App
