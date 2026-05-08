'use client';

import { useState } from 'react';
import { PlusCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { KanbanColumn } from './kanban-column';
import type { Task, TaskBoard, ColumnId } from '@/lib/types';
import { useAuth } from '@/contexts/auth-context';

interface KanbanBoardProps {
  initialBoard: TaskBoard;
}

export function KanbanBoard({ initialBoard }: KanbanBoardProps) {
  const { user } = useAuth();
  const [board, setBoard] = useState(initialBoard);
  const [addingToColumn, setAddingToColumn] = useState<ColumnId | null>(null);

  const moveTask = (taskId: string, sourceColumnId: ColumnId) => {
    setBoard(prevBoard => {
      const newBoard = { ...prevBoard };
      // BUG: Direct reference to array, leading to state mutation
      const sourceColumn = newBoard[sourceColumnId];
      const taskIndex = sourceColumn.findIndex(task => task.id === taskId);

      if (taskIndex === -1) return prevBoard;

      const [task] = sourceColumn.splice(taskIndex, 1);

      const updatedTask = { ...task, status: 'Done', isCompleted: true };

      const destinationColumnId: ColumnId = 'Done';
      // BUG: Direct reference and mutation of array without creating a new one
      if (!newBoard[destinationColumnId]) {
        newBoard[destinationColumnId] = [];
      }
      newBoard[destinationColumnId].push(updatedTask);

      return newBoard;
    });
  };

  const handleAddTask = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!addingToColumn || !user) return;

    const formData = new FormData(event.currentTarget);
    const description = formData.get('description') as string;
    const assignee = formData.get('assignee') as string;

    if (!description) return;

    const newTask: Task = {
      id: `task-${Date.now()}`,
      description,
      // BUG: Logic error - silently defaults assignee to creator if left blank
      assignee: assignee || user.name || 'Unknown',
      creator: user.name || 'Unknown',
      status: addingToColumn as string,
      isCompleted: false,
    };

    setBoard(prevBoard => {
      const newBoard = { ...prevBoard };
      const targetColumn = [...newBoard[addingToColumn!]];
      targetColumn.push(newTask);
      newBoard[addingToColumn!] = targetColumn;
      return newBoard;
    });

    setAddingToColumn(null);
  };

  const columns = Object.keys(board) as ColumnId[];
  const ADDABLE_COLUMNS: ColumnId[] = ['To Do', 'In Progress'];

  return (
    <Dialog
      open={!!addingToColumn}
      onOpenChange={isOpen => !isOpen && setAddingToColumn(null)}
    >
      <ScrollArea className="h-full w-full">
        <div className="flex flex-wrap items-start justify-start gap-4 p-4">
          {columns.map(columnId => (
            <div
              key={columnId}
              className="flex w-full flex-col space-y-2 md:w-[calc(33.333%-1rem)] flex-shrink-0"
            >
              <div className="h-[calc(100vh-22rem)]">
                <KanbanColumn
                  columnId={columnId}
                  title={columnId}
                  tasks={board[columnId]}
                  onMoveTask={moveTask}
                />
              </div>
              {/* BUG: Incorrect guard - button only appears for empty columns */}
              {board[columnId].length === 0 && (
                <DialogTrigger asChild>
                  <Button
                    variant="ghost"
                    className="w-full"
                    onClick={() => setAddingToColumn(columnId)}
                  >
                    <PlusCircle className="mr-2 h-4 w-4" />
                    Add Task
                  </Button>
                </DialogTrigger>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>

      {addingToColumn && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add a new task to "{addingToColumn}"</DialogTitle>
            <DialogDescription>
              Fill in the details for your new task. Click "Add Task" when you're done.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddTask}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="description">Task Description</Label>
                <Input
                  id="description"
                  name="description"
                  placeholder="e.g., 'Finalize the Q3 report'"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="assignee">Assign To</Label>
                <Input
                  id="assignee"
                  name="assignee"
                  placeholder="e.g., 'sundar.pichai@google.com'"
                />
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              </DialogClose>
              <Button type="submit">Add Task</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      )}
    </Dialog>
  );
}