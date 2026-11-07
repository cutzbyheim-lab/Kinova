import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { LinkButton, PageHeader } from "./components/ui";
import Brands from "./pages/Brands";
import Coming from "./pages/Coming";
import JobView from "./pages/JobView";
import Library from "./pages/Library";
import NewProduction from "./pages/NewProduction";
import Overview from "./pages/Overview";
import Settings from "./pages/Settings";
import Studio from "./pages/Studio";

function NotFound() {
  return (
    <div className="mx-auto flex max-w-[900px] flex-col gap-6">
      <PageHeader eyebrow="404" title="Cut from the" accent="final edit." />
      <div><LinkButton to="/" variant="primary">Back to Overview</LinkButton></div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="studio" element={<Studio />} />
        <Route path="studio/new" element={<NewProduction />} />
        <Route path="studio/jobs/:id" element={<JobView />} />
        <Route path="library" element={<Library />} />
        <Route path="brands" element={<Brands />} />
        <Route path="settings" element={<Settings />} />
        <Route path="campaigns" element={
          <Coming eyebrow="Campaigns" title="Ideas into" accent="campaigns."
            pitch="Describe a goal and KINOVA plans the whole campaign — concepts, posts, clips and a schedule — in your brand voice."
            points={["Campaign concepts generated from your goal and Brand Brain", "Visual content boards with cover artwork", "Clips from the Studio dropped straight into a campaign", "Status tracking from draft to published"]} />} />
        <Route path="calendar" element={
          <Coming eyebrow="Calendar" title="Plan the" accent="month."
            pitch="A visual marketing calendar: drafts, approvals and scheduled posts across every platform, at a glance."
            points={["Drag approved clips onto days", "Campaign timelines and approval states", "Platform indicators for TikTok, Reels and Shorts", "Scheduled publishing once platform accounts are connected"]} />} />
        <Route path="analytics" element={
          <Coming eyebrow="Analytics" title="What's" accent="working."
            pitch="Performance for everything you publish — views, reach and engagement — with AI recommendations on what to make next."
            points={["Connect TikTok, Instagram and YouTube through their official APIs", "Per-clip and per-campaign performance", "Trend comparisons against your topic", "Recommendations fed back into the Studio"]}
            note="KINOVA never invents numbers. This page stays empty until a real account is connected." />} />
        <Route path="assistant" element={
          <Coming eyebrow="AI assistant" title="Just" accent="ask."
            pitch="A brand-aware assistant that runs the platform for you: “Turn this video into five shorts”, “Plan a week of content”."
            points={["Natural-language requests that start real productions", "Knows your brands, projects and past results", "Generates captions, hooks and campaign ideas on demand", "Reports on what performed and why"]}
            note="Today, the Produce bar on the Overview hands your request straight to the Studio." />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
