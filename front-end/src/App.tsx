
import { BrowserRouter, Route, Routes } from "react-router"
import Analytics from "./routes/Analytics/Analytics"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Analytics />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
