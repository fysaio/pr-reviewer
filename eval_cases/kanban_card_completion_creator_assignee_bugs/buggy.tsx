import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { Task } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

interface KanbanCardProps {
  task: Task;
  onToggle: () => void;
}

export function KanbanCard({ task, onToggle }: KanbanCardProps) {
  const getInitials = (name?: string) => {
    if (!name) return "??";
    return name.split('@')[0].split('.').map(n => n[0]).join('').substring(0, 2).toUpperCase();
  }
  
  const getCreatorName = (creator?: string) => {
    if (!creator) return "Unknown";
    return creator.split(' ')[0];
  }

  const isDoneColumn = task.status === 'Done';

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-3">
        <div className="flex items-start gap-3">
          {!isDoneColumn && (
            <Checkbox
              id={`task-${task.id}`}
              checked={task.isCompleted}
              onCheckedChange={onToggle}
              className="mt-1"
            />
          )}
          <div className="flex-1 space-y-2">
            <label
              htmlFor={isDoneColumn ? undefined : `task-${task.id}`}
              className={`text-sm font-medium leading-none ${
                task.isCompleted ? 'text-muted-foreground line-through' : 'text-foreground'
              } ${isDoneColumn ? 'cursor-default' : 'cursor-pointer'}`}
            >
              {task.description}
            </label>

            <div className="flex items-center justify-between pt-1">
              {task.creator ? (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Badge variant="secondary">By {getCreatorName(task.creator)}</Badge>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Created by: {task.creator}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ) : <div />}
              
              {task.assignee && (
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger>
                            <Avatar className="h-6 w-6">
                                <AvatarImage src={`https://api.dicebear.com/8.x/avataaars/svg?seed=${task.assignee}`} />
                                <AvatarFallback>{getInitials(task.creator)}</AvatarFallback>
                            </Avatar>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>{task.assignee}</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}