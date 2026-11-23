import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./components/AuthContext";
import Dashboard from "./pages/Dashboard";
import Launches from "./pages/Launches";
import NewLaunch from "./pages/NewLaunch";
import ProductDetail from "./pages/ProductDetail";
import Agents from "./pages/Agents";
import Activity from "./pages/Activity";
import Login from "./pages/Login";
import Validation from "./pages/Validation";
import Workshops from "./pages/Workshops";
import NewWorkshop from "./pages/NewWorkshop";
import WorkshopDetail from "./pages/WorkshopDetail";
import SEODashboard from "./pages/SEODashboard";

import "./App.css";

const basename = window.location.pathname.startsWith("/static") ? "/static" : "";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter basename={basename}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Dashboard />} />
          <Route path="/launches" element={<Launches />} />
          <Route path="/launches/new" element={<NewLaunch />} />
          <Route path="/launches/:id" element={<ProductDetail />} />
          <Route path="/validation" element={<Validation />} />
          <Route path="/seo" element={<SEODashboard />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/workshops" element={<Workshops />} />
          <Route path="/workshops/new" element={<NewWorkshop />} />
          <Route path="/workshops/:id" element={<WorkshopDetail />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;

