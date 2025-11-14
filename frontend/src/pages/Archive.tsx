// src/pages/Archive.tsx
import { useEffect } from 'react'
import { Tab } from '@headlessui/react'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react'
import ReactMarkdown from 'react-markdown'
import { useStore } from '../store'
import SidebarTree from '../components/SidebarTree'

const Archive = () => {
  const { stories, selectedStory, toggleMode, loadStories } = useStore()

  useEffect(() => {
    loadStories([])  // Load root on mount
  }, [])

  // Assume subcats from stories[0].subcats or fallback
  const subcats = stories[0]?.subcats || []  // Replace with actual subcats logic if needed

  return (
    <div className="flex h-screen">
      <SidebarTree />
      <main className="flex-1 p-6 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-4">Archive</h1>
        <Tab.Group className="mb-4">
          <Tab.List className="flex space-x-4">
            {subcats.length > 0 ? subcats.map((sub) => (
              <Tab key={sub} className={({ selected }) => selected ? 'bg-blue-500 text-white px-4 py-2 rounded' : 'bg-gray-200 px-4 py-2 rounded'}>
                {sub}
              </Tab>
            )) : <p>No subcategories</p>}
          </Tab.List>
          {/* Tab.Panels for subcats content if needed */}
          <Tab.Panels>
            {subcats.map((sub) => (
              <Tab.Panel key={sub}>Content for {sub}</Tab.Panel>
            ))}
          </Tab.Panels>
        </Tab.Group>
        <div className="space-y-4">
          {stories.map((story) => (
            <Disclosure as="div" key={story.title} className="border rounded p-2">
              <DisclosureButton className="text-lg font-medium w-full text-left">
                {story.book_slug}: {story.title}
              </DisclosureButton>
              <DisclosurePanel className="mt-2">
                <ReactMarkdown>{story.html || story.text}</ReactMarkdown>
                <button onClick={() => toggleMode(story.title, story.mode === 'static' ? 'book' : 'static', story.search_query)} className="mt-2 bg-blue-500 text-white px-4 py-2 rounded">
                  Toggle to {story.mode === 'static' ? 'Book' : 'Static'}
                </button>
              </DisclosurePanel>
            </Disclosure>
          ))}
        </div>
      </main>
    </div>
  )
}

export default Archive