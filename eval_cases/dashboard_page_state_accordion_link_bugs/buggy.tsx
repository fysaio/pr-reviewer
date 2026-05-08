'use client';

import * as React from 'react';
import {
  PanelLeftClose,
  PanelLeftOpen,
  Users,
  Link as LinkIcon,
  Trash2,
  MessageSquare,
  ClipboardList,
} from 'lucide-react';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/contexts/auth-context';
import { Button } from '@/components/ui/button';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar';
import { UserNav } from '@/components/user-nav';
import { ThemeToggle } from '@/components/theme-toggle';
import { Logo } from '@/components/logo';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ChatView } from '@/components/chat-view';
import { TasksView } from '@/components/tasks-view';
import { ConversationProvider } from '@/contexts/conversation-context';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Separator } from '@/components/ui/separator';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

const initialUpcomingEvents = [
  { id: '1', title: 'Project Phoenix Kickoff', time: '10:00 AM', attendees: ['alice@example.com', 'bob@example.com'], link: 'https://meet.google.com/xyz-abc-def' },
  { id: '2', title: 'Q3 Strategy Review', time: '1:00 PM', attendees: ['charlie@example.com', 'david@example.com'], link: 'https://meet.google.com/xyz-abc-def' },
  { id: '3', title: 'Design Sync', time: '3:30 PM', attendees: ['eve@example.com', 'frank@example.com'], link: 'https://meet.google.com/xyz-abc-def' },
];

function SidebarToggleButton() {
  const { state, toggleSidebar } = useSidebar();
  const Icon = state === 'expanded' ? PanelLeftClose : PanelLeftOpen;
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleSidebar}
    >
      <Icon />
    </Button>
  );
}

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [upcomingEvents, setUpcomingEvents] = React.useState(initialUpcomingEvents);
  
  React.useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);
  
  const handleDeleteEvent = (eventId: string) => {
    setUpcomingEvents(events => {
      const index = events.findIndex(event => event.id === eventId);
      if (index > -1) {
        events.splice(index, 1); // Bug 1: Mutates the array directly instead of creating a new one
      }
      return events;
    });
  };
  
  if (loading || !user) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full">
        <Sidebar className="sticky top-0 h-screen">
          <SidebarHeader>
            <Logo />
          </SidebarHeader>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem className="px-2">
                <div className="flex w-full items-center justify-between">
                  <span className="text-sm font-medium text-muted-foreground">Upcoming Events</span>
                </div>
              </SidebarMenuItem>
               <Accordion type="multiple" collapsible className="w-full"> {/* Bug 3: Allows multiple accordion items to be open */}
                {upcomingEvents.map((event) => (
                  <AccordionItem value={event.id} key={event.id} asChild>
                    <SidebarMenuItem>
                      <div className="flex w-full items-center justify-between p-2">
                        <AccordionTrigger className="p-0 text-left">
                            <div className="flex flex-col">
                              <span className="font-semibold">{event.title}</span>
                              <span className="text-xs text-muted-foreground">{event.time}</span>
                            </div>
                        </AccordionTrigger>
                         <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0 ml-2">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This action cannot be undone. This will permanently delete this event.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDeleteEvent(event.id)}>
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                      <AccordionContent className="px-3 pb-2 text-sm text-muted-foreground">
                        <Separator className="my-2 bg-sidebar-border" />
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <Users className="h-4 w-4" />
                            <span>{Array.isArray(event.attendees) ? event.attendees.join(', ') : event.attendees}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <LinkIcon className="h-4 w-4" />
                            <a href={event.link || '/dashboard'} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline"> {/* Bug 2: Provides a generic fallback URL */}
                              Join Meeting
                            </a>
                          </div>
                        </div>
                      </AccordionContent>
                    </SidebarMenuItem>
                  </AccordionItem>
                ))}
              </Accordion>
            </SidebarMenu>
          </SidebarContent>
          <SidebarFooter>
            <UserNav user={user} onLogout={logout} />
          </SidebarFooter>
        </Sidebar>
        <div className="flex flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background/80 px-4 backdrop-blur-sm lg:h-[60px] lg:px-6">
              <SidebarTrigger className="flex md:hidden" />
              <div className="flex">
                <SidebarToggleButton />
              </div>
              <div className="w-full flex-1">
                <h1 className="text-lg font-semibold md:text-2xl">PrometheAI</h1>
              </div>
              <ThemeToggle />
          </header>
          <main className="flex flex-1 flex-col overflow-y-auto">
            <div className="w-full max-w-5xl mx-auto flex-1 flex flex-col items-center gap-4 p-4 lg:gap-6 lg:p-6">
              <div className="w-full flex-1 flex flex-col">
                <ConversationProvider>
                  <Tabs defaultValue="chat" className="flex flex-col flex-1">
                      <TabsList className="grid w-full grid-cols-2 md:w-96 self-center">
                          <TabsTrigger value="chat">
                          <MessageSquare className="mr-2 h-4 w-4" />
                          Chat
                          </TabsTrigger>
                          <TabsTrigger value="tasks">
                          <ClipboardList className="mr-2 h-4 w-4" />
                          Tasks
                          </TabsTrigger>
                      </TabsList>
                      <TabsContent value="chat" className="flex-1">
                          <ChatView />
                      </TabsContent>
                      <TabsContent value="tasks" className="flex-1">
                          <TasksView />
                      </TabsContent>
                  </Tabs>
                </ConversationProvider>
              </div>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}